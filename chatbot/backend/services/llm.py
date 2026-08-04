"""
LLM agent with tool-use for the RTA Smart Monitoring chatbot. Tools:
  - fleet_query:  structured pandas queries over alerts.csv / violations.csv
  - run_model:    the three dashboard models (forecasting, bottleneck, risk)
  - render_chart: emit a chart spec for the frontend (Recharts) to render

Returns a structured response: answer (markdown), trace (reasoning steps),
charts (specs) and status — the same shape the Health assistant uses.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

from services import data, models

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
MODEL = os.getenv("MODEL", "claude-sonnet-4-5-20250929")

_client = None


def _get_client():
    global _client
    if _client is None and ANTHROPIC_KEY:
        from anthropic import Anthropic
        _client = Anthropic(api_key=ANTHROPIC_KEY)
    return _client


# ──────────── Tool definitions ────────────

TOOLS = [
    {
        "name": "fleet_query",
        "description": (
            "Query the fleet monitoring data with structured pandas operations. Two datasets:\n"
            "  • alerts — 8.5K monitoring alerts (Operational + Staff dashboards). Columns: alert_id, "
            "timestamp, priority (low/medium/high), status (new/in_progress/escalated/fined/closed), "
            "category (vehicle type: Taxi, Public Bus, School Bus, Limousine & E-Hail, Marine, Hourly Rental), "
            "driver_id/name/company, alert_type (12 types e.g. 'Speeding >20km/h', 'Tampered Meter', "
            "'Mobile Phone Usage'), zone (15 Dubai zones), sla_met (yes/no), sla_target_hours, "
            "resolution_hours, assigned_team, operator_id/name/role.\n"
            "  • violations — 16.5K driver violations (Performance dashboard). Columns: violation_id, "
            "timestamp, latitude, longitude, zone, severity (low/moderate/high), violation_type "
            "(Speeding, Harsh Braking, Phone Use, Distraction, Route Deviation, Idling, Driver Fatigue, "
            "Lane Violation, Camera Tampering, Red Light), driver_id/name/category/company, "
            "driver_risk_score (0-10), driver_risk_label, driver_status (active/investigation/suspended).\n\n"
            "Query types:\n"
            "  • describe_dataset / describe_column — schema and stats (start here if unsure)\n"
            "  • dashboard_kpis — the exact KPI strip of a dashboard. Requires `dashboard` "
            "(performance | operational | staff).\n"
            "  • filter_rows — filter by conditions; optional `aggregate` {column, func} or `select_columns`\n"
            "  • groupby_aggregate — cross-tab, e.g. alerts by zone. Requires `group_by`; optional `metric`+`func`\n"
            "  • top_n — top/bottom rows by a column. With `unique_drivers`=true it dedupes to one row "
            "per driver and adds violation_count (use for watchlists / repeat offenders)\n"
            "  • time_series — counts over time. Optional `split_by` (e.g. severity, priority) and `freq` (D or W)\n"
            "  • histogram / correlate — distributions and Pearson correlation\n"
            "  • operator_metrics — per-operator workload, resolved, SLA breaches, avg resolution "
            "(Staff dashboard). Optional `team`, `sort_by` (total|resolved|breaches|avg_resolution_hours)\n\n"
            "Most query types accept `period_days` (7=this week, 30=month, 90=quarter) anchored to the "
            "latest data timestamp, and `filters`: list of {column, op, value} with ops "
            "==, !=, >, <, >=, <=, between, contains, not_contains, in, not_in, is_null, not_null."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "dataset": {"type": "string", "enum": ["alerts", "violations"]},
                "query_type": {
                    "type": "string",
                    "enum": ["describe_dataset", "describe_column", "dashboard_kpis", "filter_rows",
                             "groupby_aggregate", "top_n", "time_series", "histogram", "correlate",
                             "operator_metrics"],
                },
                "dashboard": {"type": "string", "enum": ["performance", "operational", "staff"]},
                "column": {"type": "string"},
                "filters": {"type": "array", "items": {"type": "object"}},
                "aggregate": {"type": "object", "description": "{column, func} — func: mean|median|sum|min|max|std"},
                "select_columns": {"type": "array", "items": {"type": "string"}},
                "group_by": {"type": "string"},
                "metric": {"type": "string"},
                "func": {"type": "string"},
                "sort_by": {"type": "string"},
                "n": {"type": "integer", "default": 10},
                "ascending": {"type": "boolean", "default": False},
                "unique_drivers": {"type": "boolean", "default": False},
                "split_by": {"type": "string"},
                "freq": {"type": "string", "enum": ["D", "W"], "default": "D"},
                "bins": {"type": "integer", "default": 10},
                "col_a": {"type": "string"},
                "col_b": {"type": "string"},
                "team": {"type": "string"},
                "limit": {"type": "integer", "default": 20},
                "period_days": {"type": "integer", "description": "Restrict to last N days of data"},
            },
            "required": ["query_type"],
        },
    },
    {
        "name": "run_model",
        "description": (
            "Run one of the three analytical models behind the dashboards:\n"
            "  • forecasting — 14-day daily alert-volume forecast (operational.html modal). "
            "Returns per-day predictions with confidence bounds, peak day, totals and a staffing "
            "recommendation. Optional `horizon_days` (1-60, default 14).\n"
            "  • bottleneck — Process Mining over the 10-stage alert-handling workflow "
            "(Validation → Supervisor Review). Returns per-stage dwell times vs the 4-minute target, "
            "the bottleneck stage and recommendations.\n"
            "  • risk — driver risk model (0-10 score; critical ≥8.0, high ≥6.5, moderate ≥3.5). "
            "`view`: summary (tier distribution) | top_drivers (riskiest drivers, watchlists) | "
            "by_group (avg risk by `group_by`: driver_category, driver_company, zone or driver_status)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "model": {"type": "string", "enum": ["forecasting", "bottleneck", "risk"]},
                "horizon_days": {"type": "integer", "default": 14},
                "view": {"type": "string", "enum": ["summary", "top_drivers", "by_group"]},
                "group_by": {"type": "string"},
                "n": {"type": "integer", "default": 10},
                "period_days": {"type": "integer"},
            },
            "required": ["model"],
        },
    },
    {
        "name": "render_chart",
        "description": (
            "Emit a chart specification to be rendered in the chat UI. Use whenever the user asks to "
            "'show', 'plot', 'visualise', 'graph' or 'compare' data, or when a chart would substantially "
            "aid understanding. Always base the data on actual fleet_query/run_model results. "
            "Preferred colors: #b91c2c (RTA red), #0e7490 (teal), #b45309 (amber), #047857 (green)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["bar", "line", "area", "pie", "scatter"]},
                "title": {"type": "string"},
                "subtitle": {"type": "string"},
                "data": {"type": "array", "items": {"type": "object"},
                         "description": "Row objects, e.g. [{'zone':'Deira','alerts':794}]"},
                "xKey": {"type": "string"},
                "yKeys": {
                    "type": "array",
                    "items": {"type": "object", "properties": {
                        "key": {"type": "string"}, "label": {"type": "string"}, "color": {"type": "string"}}},
                },
                "annotations": {"type": "array", "items": {"type": "object"},
                                "description": "e.g. [{'type':'reference','value':4,'label':'Target'}]"},
                "yAxisLabel": {"type": "string"},
                "footnote": {"type": "string"},
            },
            "required": ["type", "title", "data", "xKey", "yKeys"],
        },
    },
]


# ──────────── Tool executors ────────────

def execute_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == "fleet_query":
        qt = args.get("query_type")
        ds = args.get("dataset", "alerts")
        pd_days = args.get("period_days")
        filters = args.get("filters") or None
        if qt == "describe_dataset":
            return data.describe_dataset(ds)
        if qt == "describe_column":
            return data.describe_column(ds, args.get("column", ""))
        if qt == "dashboard_kpis":
            dash = args.get("dashboard", "operational")
            fn = {"performance": data.performance_kpis, "operational": data.operational_kpis,
                  "staff": data.staff_kpis}.get(dash)
            return fn(pd_days) if fn else {"error": f"unknown dashboard: {dash}"}
        if qt == "filter_rows":
            return data.filter_rows(ds, filters, args.get("select_columns"),
                                    args.get("aggregate"), args.get("limit", 20), pd_days)
        if qt == "groupby_aggregate":
            return data.groupby_aggregate(ds, args.get("group_by", ""), args.get("metric"),
                                          args.get("func", "count"), filters,
                                          args.get("n") or 30, pd_days)
        if qt == "top_n":
            return data.top_n(ds, args.get("sort_by", ""), args.get("n", 10),
                              args.get("ascending", False), filters, args.get("select_columns"),
                              pd_days, args.get("unique_drivers", False))
        if qt == "time_series":
            return data.time_series(ds, pd_days or 30, args.get("freq", "D"),
                                    args.get("split_by"), filters)
        if qt == "histogram":
            return data.histogram(ds, args.get("column", ""), args.get("bins", 10), filters, pd_days)
        if qt == "correlate":
            return data.correlate(ds, args.get("col_a", ""), args.get("col_b", ""))
        if qt == "operator_metrics":
            return {"rows": data.operator_metrics(pd_days, args.get("team"),
                                                  args.get("sort_by") or "total", args.get("n", 24))}
        return {"error": f"unknown query_type: {qt}"}

    if name == "run_model":
        m = args.get("model")
        if m == "forecasting":
            return models.forecast_alert_volume(args.get("horizon_days", 14))
        if m == "bottleneck":
            return models.bottleneck_analysis()
        if m == "risk":
            return models.risk_model(args.get("view", "summary"), args.get("n", 10),
                                     args.get("period_days"), args.get("group_by"))
        return {"error": f"unknown model: {m}"}

    if name == "render_chart":
        return {"ok": True, "chart_id": f"c_{int(time.time() * 1000)}"}

    return {"error": f"unknown tool: {name}"}


# ──────────── Agent loop ────────────

SYSTEM_PROMPT = """You are the RTA Smart Monitoring Assistant — a data-analysis AI agent for the Roads and Transport Authority (RTA) Dubai Smart Monitoring Centre. You operate on top of the live fleet-monitoring data behind three dashboards and three analytical models.

YOUR SCOPE — you answer questions about, and only about:
1. PERFORMANCE dashboard (performance.html) — driver violations: 16.5K records in violations.csv. Violation types, severity, zones, driver risk scores/tiers, driver status (active/investigation/suspended), companies, vehicle categories.
2. OPERATIONAL dashboard (operational.html) — monitoring alerts: 8.5K records in alerts.csv. Alert priority/status lifecycle (new → in_progress → escalated → fined → closed), SLA compliance, resolution times, zones, assigned teams.
3. STAFF dashboard (staff.html) — operator performance: the 24-operator roster across 6 teams joined to alerts.csv. Workload, resolution rates, SLA breaches, performance tiers.
4. THE THREE MODELS — forecasting (14-day alert volume), bottleneck/process mining (10-stage alert workflow), and driver risk (0-10 scoring).

If a question is outside this scope (other dashboards, other datasets, or unrelated topics), politely say it is outside the monitoring data you cover and steer the user back — do not answer from general knowledge.

Agentic behavior:
1. Think step-by-step about what data you need; never invent figures — every number must come from a tool call.
2. Use `fleet_query` for any data question. If unsure what's available, call describe_dataset first. Use `dashboard_kpis` when the user asks about a dashboard's headline numbers so your figures match what they see on screen.
3. Use `run_model` for forecasting, bottleneck/process-mining, and risk questions.
4. Use `render_chart` whenever the user asks to see/plot/compare data, or when a chart makes the answer substantially clearer. Pick the simplest chart type that fits. Use the RTA palette (#b91c2c red, #0e7490 teal, #b45309 amber, #047857 green) and map severity/priority sensibly (high=red, medium/moderate=amber, low=teal or green).
5. Give RECOMMENDATIONS when asked (or when clearly useful): concrete, operational, and grounded in the numbers you just queried — e.g. staffing shifts, watchlists, SLA process fixes, automation of the manual fine path. Put them under a "**Recommendations**" heading as short bullets.
6. "This week / this month / this quarter" → period_days 7 / 30 / 90. Data is anchored to the latest record timestamp (late May 2026), not the wall clock.

Answer format: clean markdown. Use **bold** for key figures, short sentences, bullet points sparingly, and small tables when comparing a handful of items. Lead with the answer, then supporting detail.
"""

WELCOME = ("Hi — I'm the RTA Smart Monitoring Assistant, grounded in your Performance, Operational and "
           "Staff dashboards. I can analyse violations, alerts, SLA compliance and operator workload, run "
           "the forecasting, bottleneck and risk models, build charts, and give recommendations. "
           "What would you like to look at?")


def run_agent(query: str, history: list[dict[str, str]] | None = None,
              max_iters: int = 8) -> dict[str, Any]:
    client = _get_client()
    if client is None:
        return _no_key_response()

    messages: list[dict[str, Any]] = []
    if history:
        for h in history[-6:]:
            if h.get("role") in ("user", "assistant") and h.get("content"):
                messages.append({"role": h["role"], "content": str(h["content"])[:800]})
    messages.append({"role": "user", "content": query})

    trace: list[dict[str, Any]] = []
    charts: list[dict[str, Any]] = []
    final_text = ""

    for _ in range(max_iters):
        resp = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        text_parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
        if text_parts:
            final_text = "\n".join(text_parts).strip()

        tool_uses = [b for b in resp.content if getattr(b, "type", None) == "tool_use"]
        if not tool_uses:
            break

        messages.append({"role": "assistant", "content": resp.content})
        tool_results: list[dict[str, Any]] = []
        for tu in tool_uses:
            args = tu.input or {}
            t0 = time.time()
            try:
                result = execute_tool(tu.name, args)
            except Exception as e:
                result = {"error": str(e)[:300]}
            ms = int((time.time() - t0) * 1000)

            trace.append({
                "agent": _agent_for(tu.name, args),
                "tool": tu.name,
                "description": _summarise_args(tu.name, args),
                "detail": _summarise_result(tu.name, result),
                "duration_ms": ms,
            })
            if tu.name == "render_chart":
                charts.append({**args})

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": json.dumps(result, default=str)[:4000],
            })
        messages.append({"role": "user", "content": tool_results})

    return {
        "answer": final_text or "I wasn't able to produce an answer for that query.",
        "trace": trace,
        "charts": charts,
        "status": "answered" if final_text else "no_answer",
    }


def _agent_for(tool: str, args: dict) -> str:
    if tool == "fleet_query":
        return "fleet_agent"
    if tool == "render_chart":
        return "analytics_agent"
    return {"forecasting": "forecast_engine", "bottleneck": "process_mining",
            "risk": "risk_model"}.get(args.get("model", ""), "model_engine")


def _summarise_args(tool: str, args: dict) -> str:
    if tool == "fleet_query":
        qt = args.get("query_type", "")
        ds = args.get("dataset", "alerts")
        if qt == "dashboard_kpis":
            return f"Pulling {args.get('dashboard', '?')} dashboard KPIs"
        return f"Querying {ds} dataset: {qt}"
    if tool == "run_model":
        m = args.get("model", "?")
        if m == "forecasting":
            return f"Running {args.get('horizon_days', 14)}-day alert volume forecast"
        if m == "bottleneck":
            return "Running process mining over the 10-stage alert workflow"
        return f"Running driver risk model ({args.get('view', 'summary')})"
    if tool == "render_chart":
        return f"Rendering {args.get('type', '?')} chart: '{args.get('title', '')}'"
    return f"Calling {tool}"


def _summarise_result(tool: str, result: dict) -> str:
    if "error" in result:
        return f"Error: {result['error']}"
    if tool == "fleet_query":
        if "rows" in result:
            return f"Retrieved {len(result['rows'])} rows"
        if "matched" in result:
            return f"Matched {result['matched']} records"
        return "Aggregated stats computed"
    if tool == "run_model":
        if result.get("model") == "alert_volume_forecast":
            return f"Forecast total: {result['insights']['total_forecast']:,} alerts over {result['horizon_days']} days"
        if result.get("model") == "process_mining_bottleneck":
            return f"Bottleneck: {result['bottleneck']['stage']} ({result['bottleneck']['avg_minutes']}m)"
        if "rows" in result:
            return f"Scored {len(result['rows'])} groups/drivers"
        return f"Risk distribution computed across {result.get('total_drivers', '?')} drivers"
    if tool == "render_chart":
        return "Chart spec emitted to frontend"
    return ""


def _no_key_response() -> dict[str, Any]:
    return {
        "answer": ("**Free-form chat requires an Anthropic API key.** "
                   "Set `ANTHROPIC_API_KEY` in `chatbot/backend/.env` (see `.env.example`) and restart the backend."),
        "trace": [],
        "charts": [],
        "status": "answered",
    }
