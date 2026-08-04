"""
LLM agent with tool-use for the Dubai Police Smart Assistant. Tools:
  - police_query: structured pandas queries over the three dashboard datasets
  - run_model:    the three dashboard models (forecasting, risk, segmentation)
  - render_chart: emit a chart spec for the frontend (Recharts) to render

Returns a structured response: answer (markdown), trace (reasoning steps),
charts (specs) and status.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

from services import data, models

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
MODEL = os.getenv("MODEL", "claude-opus-5")

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
        "name": "police_query",
        "description": (
            "Query the Dubai Police dangerous-drivers data with structured pandas operations. "
            "Three datasets, all joined on TRAFFIC_NO (رقم الملف المروري) — 750 dangerous drivers "
            "appear in each:\n"
            "  • violations — 2,462 traffic violations (overview dashboard). Columns: TRAFFIC_NO, "
            "TICKET_NO, TICKET_DATE, OFFENCE_DESCRIPTION / OFFENCE_DESCRIPTION_A (Arabic), "
            "OFFENCE_SCORE (25–95), RISK_SCORE (0–1 = score/100), TOTAL_FINE (AED), "
            "DANGER_CATEGORY_DESC (low/medium/dangerous/highly dangerous), NAME / NAME_A, "
            "CNT_DESCRIPTION / CNT_DESCRIPTION_A (nationality), GENDER_DESC (ذكر/أنثى), AGE, AGE_BAND, "
            "OCCUPATION_DESC, SPONSOR_NAME / SPONSOR_NAME_A, ORG_NAME, ORG_ACTIVITY, LIC_Type, "
            "LIC_ISSUED_INSTITUTE, EXAMINER_NAME, LIC_SOURCE, LICENSE_NUMBER, PLATE_NO, "
            "PLATE_CATEGORY_DESC, PLATE_COLOR_DESC, PLC_EMI_CODE (plate emirate: DXB/AUH/SHJ/...), "
            "LOCATION_DESC_E / LOCATION_DESC_A, NEIGHBORHOOD_E / NEIGHBORHOOD_A, GPS_LATITUDE, "
            "GPS_LONGITUDE, VEHICLE_COUNT, EXPIRED_VEHICLES, IMPOUNDED_VEHICLES, WANTED_VEHICLES, "
            "CRIMINAL_PRIORS.\n"
            "  • cases — 1,105 rows of the criminal-reports dashboard: 612 criminal reports "
            "(HAS_CRIMINAL_REPORT='بلاغ جنائي') + 493 drivers without reports. Columns: TRAFFIC_NO, "
            "NAME / NAME_A, CASE_DATE, CRIME (Arabic charge, 50 types e.g. 'السب والقذف', "
            "'القيادة بسرعة جنونية'), CASE_CATEGORY ('مقلقة' concerning / 'غير مقلقة' non-concerning), "
            "DANGER_CATEGORY_DESC, HAS_CRIMINAL_REPORT.\n"
            "  • movements — 750 rows, one per driver (movements dashboard): TRAFFIC_NO, NAME_A, "
            "NATIONALITY_A, OCCUPATION, UNIFIED_NO, BORDER_STATUS ('داخل الدولة'/'خارج الدولة'), "
            "BORDER_STATUS_E (inside_country/outside_country), LAST_CROSSING_DATE, PRIORS "
            "('توجد'/'لاتوجد'/'متوفى'), PRIORS_E, VEHICLE_COUNT, ACTIVE_VEHICLES, EXPIRED_VEHICLES, "
            "VEHICLES_MOVING, VEHICLES_IDLE.\n\n"
            "Query types:\n"
            "  • describe_dataset / describe_column — schema and stats (start here if unsure)\n"
            "  • dashboard_kpis — the exact KPI strip of a dashboard. Requires `dashboard` "
            "(overview | cases | movements).\n"
            "  • driver_profile — full cross-dataset profile card (البطاقة التعريفية) for one driver. "
            "Requires `identifier`: traffic file number or name (Arabic or English). Returns identity, "
            "license, risk score, violations, vehicles, criminal reports and border status.\n"
            "  • filter_rows — filter by conditions; optional `aggregate` {column, func} or `select_columns`\n"
            "  • groupby_aggregate — cross-tab, e.g. violations by NEIGHBORHOOD_E. Requires `group_by`; "
            "optional `metric`+`func` (sum/mean/...)\n"
            "  • top_n — top/bottom rows by a column. On `violations` with `unique_drivers`=true it "
            "aggregates to one row per driver (RISK_SCORE, violation_count, total_fines_aed) — use for "
            "rankings and watchlists\n"
            "  • time_series — counts over time. Optional `split_by` and `freq` (D, W, M, Q, Y). "
            "violations→TICKET_DATE, cases→CASE_DATE, movements→LAST_CROSSING_DATE\n"
            "  • histogram / correlate — distributions and Pearson correlation\n\n"
            "Most query types accept `period_days` (30=month, 90=quarter, 365=year) anchored to the "
            "latest data timestamp, and `filters`: list of {column, op, value} with ops "
            "==, !=, >, <, >=, <=, between, contains, not_contains, in, not_in, is_null, not_null. "
            "Arabic values must match exactly (e.g. CASE_CATEGORY == 'مقلقة')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "dataset": {"type": "string", "enum": ["violations", "cases", "movements"]},
                "query_type": {
                    "type": "string",
                    "enum": ["describe_dataset", "describe_column", "dashboard_kpis",
                             "driver_profile", "filter_rows", "groupby_aggregate", "top_n",
                             "time_series", "histogram", "correlate"],
                },
                "dashboard": {"type": "string", "enum": ["overview", "cases", "movements"]},
                "identifier": {"type": "string",
                               "description": "driver_profile: traffic file no. or name (AR/EN)"},
                "column": {"type": "string"},
                "filters": {"type": "array", "items": {"type": "object"}},
                "aggregate": {"type": "object",
                              "description": "{column, func} — func: mean|median|sum|min|max|std"},
                "select_columns": {"type": "array", "items": {"type": "string"}},
                "group_by": {"type": "string"},
                "metric": {"type": "string"},
                "func": {"type": "string"},
                "sort_by": {"type": "string"},
                "n": {"type": "integer", "default": 10},
                "ascending": {"type": "boolean", "default": False},
                "unique_drivers": {"type": "boolean", "default": False},
                "split_by": {"type": "string"},
                "freq": {"type": "string", "enum": ["D", "W", "M", "Q", "Y"], "default": "M"},
                "bins": {"type": "integer", "default": 10},
                "col_a": {"type": "string"},
                "col_b": {"type": "string"},
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
            "  • forecasting — THE SAME forecast as the dashboard's 'الذكاء الاصطناعي والتنبؤ' card: "
            "OLS linear trend on distinct drivers per registration year (2022–2026, the partial "
            "final year excluded from the fit) with a 95% prediction interval; the headline is "
            "rounded to the nearest 100 (~700 by 2030). Also returns the card's narrative figures: "
            "1,767 drivers on the risk list, 53.5% high-risk share. Optional `horizon_year` "
            "(default 2030) and `confidence` (80|90|95|99).\n"
            "  • risk — driver risk model (0–1 score = avg OFFENCE_SCORE/100; fleet average 0.57). "
            "`view`: summary (category distribution + gauge) | top_drivers (riskiest drivers) | "
            "by_group (avg risk by `group_by`: NATIONALITY, OCCUPATION_DESC, SPONSOR_NAME, ORG_NAME, "
            "ORG_ACTIVITY, LIC_ISSUED_INSTITUTE, LIC_TYPE, GENDER_DESC, AGE_BAND, PLATE_EMIRATE) | "
            "watchlist (cross-dataset: dangerous drivers with concerning criminal reports who are "
            "currently inside the country — use for 'who should we act on first').\n"
            "  • segmentation — driver profile segmentation (the Sankey panel): per danger category, "
            "the distribution across age band, nationality, gender, vehicle class, occupation. "
            "Optional `dimension` to focus on one."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "model": {"type": "string", "enum": ["forecasting", "risk", "segmentation"]},
                "horizon_year": {"type": "integer", "default": 2030},
                "confidence": {"type": "integer", "enum": [80, 90, 95, 99], "default": 95},
                "view": {"type": "string",
                         "enum": ["summary", "top_drivers", "by_group", "watchlist"]},
                "group_by": {"type": "string"},
                "dimension": {"type": "string"},
                "n": {"type": "integer", "default": 10},
            },
            "required": ["model"],
        },
    },
    {
        "name": "render_chart",
        "description": (
            "Emit a chart specification to be rendered in the chat UI. Use whenever the user asks to "
            "'show', 'plot', 'visualise', 'graph', 'اعرض', 'ارسم' or 'compare' data, or when a chart "
            "would substantially aid understanding. Always base the data on actual police_query/"
            "run_model results. Preferred colors (dark theme): #2dd4a7 (police green), #38bdf8 (blue), "
            "#f0b429 (amber), #ef5350 (red), #a78bfa (violet). Map danger sensibly: "
            "highly dangerous=red, dangerous=amber, medium=blue, low=green."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["bar", "line", "area", "pie", "scatter"]},
                "title": {"type": "string"},
                "subtitle": {"type": "string"},
                "data": {"type": "array", "items": {"type": "object"},
                         "description": "Row objects, e.g. [{'category':'خطير','drivers':176}]"},
                "xKey": {"type": "string"},
                "yKeys": {
                    "type": "array",
                    "items": {"type": "object", "properties": {
                        "key": {"type": "string"}, "label": {"type": "string"},
                        "color": {"type": "string"}}},
                },
                "annotations": {"type": "array", "items": {"type": "object"},
                                "description": "e.g. [{'type':'reference','value':0.57,'label':'Average'}]"},
                "yAxisLabel": {"type": "string"},
                "footnote": {"type": "string"},
            },
            "required": ["type", "title", "data", "xKey", "yKeys"],
        },
    },
]


# ──────────── Tool executors ────────────

def execute_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == "police_query":
        qt = args.get("query_type")
        ds = args.get("dataset", "violations")
        pd_days = args.get("period_days")
        filters = args.get("filters") or None
        if qt == "describe_dataset":
            return data.describe_dataset(ds)
        if qt == "describe_column":
            return data.describe_column(ds, args.get("column", ""))
        if qt == "dashboard_kpis":
            dash = args.get("dashboard", "overview")
            if dash == "overview":
                return data.overview_kpis(pd_days)
            if dash == "cases":
                return data.cases_kpis()
            if dash == "movements":
                return data.movements_kpis()
            return {"error": f"unknown dashboard: {dash}"}
        if qt == "driver_profile":
            return data.driver_profile(args.get("identifier", ""))
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
            return data.time_series(ds, pd_days, args.get("freq", "M"),
                                    args.get("split_by"), filters)
        if qt == "histogram":
            return data.histogram(ds, args.get("column", ""), args.get("bins", 10), filters, pd_days)
        if qt == "correlate":
            return data.correlate(ds, args.get("col_a", ""), args.get("col_b", ""))
        return {"error": f"unknown query_type: {qt}"}

    if name == "run_model":
        m = args.get("model")
        if m == "forecasting":
            return models.forecast_dangerous_drivers(args.get("horizon_year", 2030),
                                                     args.get("confidence", 95))
        if m == "risk":
            return models.risk_model(args.get("view", "summary"), args.get("n", 10),
                                     args.get("group_by"))
        if m == "segmentation":
            return models.segmentation(args.get("dimension"), args.get("n", 5))
        return {"error": f"unknown model: {m}"}

    if name == "render_chart":
        return {"ok": True, "chart_id": f"c_{int(time.time() * 1000)}"}

    return {"error": f"unknown tool: {name}"}


# ──────────── Agent loop ────────────

SYSTEM_PROMPT = """You are the Smart Assistant (المساعد الذكي) of the Dubai Police Security Analytics & Forecast Center (مركز التحليل والتنبؤ الأمني). You operate on top of the live dangerous-drivers data behind four dashboard pages and three analytical models.

YOUR SCOPE — you answer questions about, and only about:
1. DANGEROUS DRIVERS OVERVIEW — 2,462 traffic violations by 750 dangerous drivers (TRF_DANGEROUS_JOIN_V3). Violation types, fines (7.87M AED total), danger categories (low/medium/dangerous/highly dangerous), risk scores, locations, plate emirates, sponsors, organizations.
2. DRIVER PROFILE CARD (البطاقة التعريفية للسائق الخطر) — per-driver lookup by traffic file number (رقم الملف المروري) or name: identity, license and driving institute, risk score, violations, vehicles (expired/impounded/wanted), criminal record, border status.
3. CRIMINAL REPORTS (البلاغات الجنائية) — 1,105 rows: 612 criminal reports across 50 charges, classified concerning (مقلقة, 353) / non-concerning (غير مقلقة, 259).
4. MOVEMENTS (التحركات) — 750 persons: inside/outside country (374/376), border crossings, vehicles (4,808), priors (السوابق), occupations, nationalities.
5. THE THREE MODELS — forecasting, risk (0–1 scoring, fleet avg 0.57), and segmentation (danger category × demographic profiles). The risk model's watchlist view cross-references all three datasets.

THE FORECAST: the forecasting model is the exact engine behind the dashboard's "الذكاء الاصطناعي والتنبؤ" card — an ordinary-least-squares linear trend on distinct drivers per registration year, with the partial final year (2026) excluded from the fit and a 95% prediction interval. Its headline matches the dashboard word for word: ~700 dangerous drivers by 2030, 1,767 drivers on the risk list, 53.5% high-risk. When asked about "the forecast on the dashboard", use this model — the numbers will match what the user sees on screen. If asked about methodology, be honest: it is a linear trend with a prediction interval, not SAS VA's ARIMA forecast object.

If a question is outside this scope (other police departments, other datasets, or unrelated topics), politely say it is outside the data you cover and steer the user back — do not answer from general knowledge.

LANGUAGE: Answer in the language of the user's question — Arabic questions get Arabic answers, English questions get English answers. The data contains both Arabic and English fields; prefer the Arabic field (e.g. OFFENCE_DESCRIPTION_A, NAME_A) when answering in Arabic and the English one when answering in English. Amounts are in AED (درهم).

Agentic behavior:
1. Think step-by-step about what data you need; never invent figures — every number must come from a tool call.
2. Use `police_query` for any data question. If unsure what's available, call describe_dataset first. Use `dashboard_kpis` when the user asks about a dashboard's headline numbers so your figures match what they see on screen. Use `driver_profile` whenever the user asks about a specific driver.
3. Use `run_model` for forecasting, risk-scoring, segmentation and watchlist questions.
4. Use `render_chart` whenever the user asks to see/plot/compare data, or when a chart makes the answer substantially clearer. Pick the simplest chart type that fits. Use the dark-theme palette (#2dd4a7 green, #38bdf8 blue, #f0b429 amber, #ef5350 red) and map danger categories sensibly (highly dangerous=red, dangerous=amber, medium=blue, low=green).
5. Give RECOMMENDATIONS when asked (or when clearly useful): concrete, operational, and grounded in the numbers you just queried — e.g. priority watchlists, border-alert candidates, licensing-institute reviews, sponsor/company follow-ups. Put them under a "**Recommendations**" / "**التوصيات**" heading as short bullets.
6. "This month / this quarter / this year" → period_days 30 / 90 / 365. Data is anchored to the latest violation date (July 2026), not the wall clock.

Answer format: clean markdown. Use **bold** for key figures, short sentences, bullet points sparingly, and small tables when comparing a handful of items. Lead with the answer, then supporting detail.
"""

WELCOME = ("Hi — I'm the Smart Assistant of the Dubai Police Security Analytics & Forecast Center. "
           "I can analyse dangerous drivers, violations, criminal reports and movements, look up "
           "driver profile cards, run the forecasting, risk and segmentation models, build charts "
           "and give recommendations — in English or Arabic. What would you like to look at?")


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
            max_tokens=8192,
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
                "content": json.dumps(result, ensure_ascii=False, default=str)[:6000],
            })
        messages.append({"role": "user", "content": tool_results})

    return {
        "answer": final_text or "I wasn't able to produce an answer for that query.",
        "trace": trace,
        "charts": charts,
        "status": "answered" if final_text else "no_answer",
    }


def _agent_for(tool: str, args: dict) -> str:
    if tool == "police_query":
        return "police_data_agent"
    if tool == "render_chart":
        return "analytics_agent"
    return {"forecasting": "forecast_engine", "risk": "risk_model",
            "segmentation": "segmentation_engine"}.get(args.get("model", ""), "model_engine")


def _summarise_args(tool: str, args: dict) -> str:
    if tool == "police_query":
        qt = args.get("query_type", "")
        ds = args.get("dataset", "violations")
        if qt == "dashboard_kpis":
            return f"Pulling {args.get('dashboard', 'overview')} dashboard KPIs"
        if qt == "driver_profile":
            return f"Building driver profile card for '{args.get('identifier', '?')}'"
        return f"Querying {ds} dataset: {qt}"
    if tool == "run_model":
        m = args.get("model", "?")
        if m == "forecasting":
            return f"Running dangerous-drivers forecast to {args.get('horizon_year', 2030)}"
        if m == "segmentation":
            return "Running driver segmentation across profile dimensions"
        return f"Running driver risk model ({args.get('view', 'summary')})"
    if tool == "render_chart":
        return f"Rendering {args.get('type', '?')} chart: '{args.get('title', '')}'"
    return f"Calling {tool}"


def _summarise_result(tool: str, result: dict) -> str:
    if "error" in result:
        return f"Error: {result['error']}"
    if tool == "police_query":
        if "traffic_no" in result:
            return f"Profile assembled for traffic file {result['traffic_no']}"
        if "multiple_matches" in result:
            return f"{len(result['multiple_matches'])} drivers match — need disambiguation"
        if "rows" in result:
            return f"Retrieved {len(result['rows'])} rows"
        if "matched" in result:
            return f"Matched {result['matched']} records"
        return "Aggregated stats computed"
    if tool == "run_model":
        if result.get("model") == "dangerous_drivers_forecast":
            return f"Forecast: ~{result['insights']['forecast_headline']} drivers by {result['horizon_year']}"
        if result.get("view") == "watchlist":
            return f"Watchlist: {result['matching_drivers_inside_country']} priority drivers inside the country"
        if result.get("model") == "driver_segmentation":
            return f"Segmented drivers across {len(result['dimensions'])} dimensions"
        if "rows" in result:
            return f"Scored {len(result['rows'])} groups/drivers"
        return f"Risk distribution computed across {result.get('total_drivers', '?')} drivers"
    if tool == "render_chart":
        return "Chart spec emitted to frontend"
    return ""


def _no_key_response() -> dict[str, Any]:
    return {
        "answer": ("**Free-form chat requires an Anthropic API key.** "
                   "Set `ANTHROPIC_API_KEY` in `chatbot/backend/.env` (see `.env.example`) "
                   "and restart the backend."),
        "trace": [],
        "charts": [],
        "status": "answered",
    }
