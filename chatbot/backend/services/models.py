"""
The three analytical models surfaced on the dashboards:

  - forecasting  → operational.html's 14-day alert-volume forecast modal
  - bottleneck   → operational.html's Process Mining (workflow bottleneck) modal
  - risk         → performance.html's driver risk scoring (driver_risk_score 0–10)

Forecast and bottleneck reproduce the dashboards' logic exactly so the chatbot's
numbers match what the user sees on screen.
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd

from services import data

# ──────────── Forecasting model (operational.html) ────────────
# Base 2300 alerts/day, weekend dip to 58%, Friday 86%, a ±6% sinusoidal wave
# and a +22 alerts/day linear trend. Confidence band is ±18%.

def forecast_alert_volume(horizon_days: int = 14) -> dict[str, Any]:
    horizon_days = max(1, min(int(horizon_days or 14), 60))
    anchor = data.data_now("alerts").normalize()
    days = []
    for i in range(horizon_days):
        d = anchor + pd.Timedelta(days=i + 1)  # starts tomorrow
        weekday = d.dayofweek                  # Mon=0 … Sun=6
        weekend = weekday in (5, 6)            # Sat/Sun
        factor = 0.58 if weekend else (0.86 if weekday == 4 else 1.0)  # Friday dip
        wave = 1 + 0.06 * math.sin(i / 1.7)
        value = max(400, round(2300 * factor * wave + i * 22))
        days.append({
            "date": str(d.date()),
            "day": d.strftime("%a"),
            "predicted_alerts": value,
            "lower_bound": round(value * 0.82),
            "upper_bound": round(value * 1.18),
            "weekend": weekend,
        })
    peak = max(days, key=lambda x: x["predicted_alerts"])
    weekend_days = [x for x in days if x["weekend"]]
    weekday_days = [x for x in days if not x["weekend"]]
    return {
        "model": "alert_volume_forecast",
        "horizon_days": horizon_days,
        "anchor_date": str(anchor.date()),
        "days": days,
        "insights": {
            "peak_day": {"date": peak["date"], "day": peak["day"], "predicted_alerts": peak["predicted_alerts"]},
            "total_forecast": sum(x["predicted_alerts"] for x in days),
            "weekday_avg": round(sum(x["predicted_alerts"] for x in weekday_days) / max(len(weekday_days), 1)),
            "weekend_avg": round(sum(x["predicted_alerts"] for x in weekend_days) / max(len(weekend_days), 1)) if weekend_days else 0,
            "staffing_recommendation": "Add +2 operators on peak weekdays; weekend volume runs ~42% below weekday baseline.",
        },
        "methodology": "Seasonal baseline (weekday/weekend), sinusoidal demand wave (±6%) and linear growth trend (+22 alerts/day); ±18% confidence band.",
    }


# ──────────── Bottleneck / Process Mining model (operational.html) ────────────
# 10-stage alert-handling workflow with per-stage dwell times in minutes.

BOTTLENECK_TARGET_MIN = 4.0
BOTTLENECK_STAGES = [
    {"stage": "Validation",            "owner": "Operator",   "avg_minutes": 2.1,  "status": "green", "trend": "0%"},
    {"stage": "Close / Acknowledge",   "owner": "Operator",   "avg_minutes": 3.4,  "status": "green", "trend": "-5%"},
    {"stage": "Notify Driver",         "owner": "Auto-meter", "avg_minutes": 1.8,  "status": "green", "trend": "-12%"},
    {"stage": "Fine Decision",         "owner": "Operator",   "avg_minutes": 4.6,  "status": "amber", "trend": "+8%"},
    {"stage": "Issue Fine (Manual)",   "owner": "STafteesh",  "avg_minutes": 12.4, "status": "red",   "trend": "+38%", "bottleneck": True},
    {"stage": "Issue Fine (Auto)",     "owner": "STafteesh",  "avg_minutes": 3.2,  "status": "green", "trend": "-4%"},
    {"stage": "Suspend via STafteesh", "owner": "STafteesh",  "avg_minutes": 5.1,  "status": "amber", "trend": "0%"},
    {"stage": "Suspend via Teams",     "owner": "Supervisor", "avg_minutes": 6.7,  "status": "amber", "trend": "+11%"},
    {"stage": "Investigation Office",  "owner": "Routing",    "avg_minutes": 2.3,  "status": "green", "trend": "0%"},
    {"stage": "Supervisor Review",     "owner": "Escalation", "avg_minutes": 8.2,  "status": "amber", "trend": "+6%"},
]


def bottleneck_analysis() -> dict[str, Any]:
    worst = max(BOTTLENECK_STAGES, key=lambda s: s["avg_minutes"])
    over = [s for s in BOTTLENECK_STAGES if s["avg_minutes"] > BOTTLENECK_TARGET_MIN]
    return {
        "model": "process_mining_bottleneck",
        "target_minutes_per_stage": BOTTLENECK_TARGET_MIN,
        "stages": BOTTLENECK_STAGES,
        "bottleneck": worst,
        "stages_over_target": [s["stage"] for s in over],
        "total_cycle_minutes": round(sum(s["avg_minutes"] for s in BOTTLENECK_STAGES), 1),
        "insights": {
            "headline": f"'{worst['stage']}' is the primary bottleneck at {worst['avg_minutes']}m per alert "
                        f"({worst['avg_minutes'] / BOTTLENECK_TARGET_MIN:.1f}× the {BOTTLENECK_TARGET_MIN}m target), trending {worst['trend']}.",
            "recommendation": "Shift manual fine issuance to the automated STafteesh path (3.2m, trending -4%); "
                              "review Supervisor Review (8.2m) and Suspend via Teams (6.7m) queues next.",
        },
    }


# ──────────── Risk model (performance.html) ────────────
# driver_risk_score (0–10) from violations.csv, bucketed with the dashboard's tiers.

def risk_model(view: str = "summary", n: int = 10, period_days: int | None = None,
               group_by: str | None = None) -> dict[str, Any]:
    df = data.get_rows("violations", period_days=period_days)
    counts = df.groupby("driver_id").size()
    drivers = df.sort_values("_ts").drop_duplicates("driver_id", keep="last").copy()
    drivers["violation_count"] = drivers["driver_id"].map(counts)
    drivers["risk_tier"] = drivers["driver_risk_score"].apply(data.risk_tier)

    if view == "top_drivers":
        cols = ["driver_id", "driver_name", "driver_category", "driver_company",
                "driver_risk_score", "risk_tier", "driver_status", "violation_count", "zone"]
        rows = drivers.sort_values("driver_risk_score", ascending=False).head(n)[cols]
        return {"model": "driver_risk", "view": view,
                "rows": [{k: data._clean(v) for k, v in r.items()} for r in rows.to_dict("records")]}

    if view == "by_group":
        col = group_by if group_by in ("driver_category", "driver_company", "zone", "driver_status") else "driver_category"
        g = drivers.groupby(col).agg(
            drivers=("driver_id", "count"),
            avg_risk_score=("driver_risk_score", "mean"),
            high_risk_drivers=("risk_tier", lambda s: int(s.isin(["critical", "high"]).sum())),
        ).sort_values("avg_risk_score", ascending=False)
        rows = [{col: str(k), "drivers": int(r["drivers"]),
                 "avg_risk_score": round(float(r["avg_risk_score"]), 2),
                 "high_risk_drivers": int(r["high_risk_drivers"])} for k, r in g.iterrows()]
        return {"model": "driver_risk", "view": view, "group_by": col, "rows": rows[:30]}

    # default: summary / distribution
    tiers = drivers["risk_tier"].value_counts()
    return {
        "model": "driver_risk", "view": "summary",
        "tier_thresholds": {"critical": ">= 8.0", "high": ">= 6.5", "moderate": ">= 3.5", "low": "< 3.5"},
        "total_drivers": len(drivers),
        "avg_risk_score": round(float(drivers["driver_risk_score"].mean()), 2),
        "distribution": {t: int(tiers.get(t, 0)) for t in ("critical", "high", "moderate", "low")},
        "status_counts": {str(k): int(v) for k, v in drivers["driver_status"].value_counts().items()},
    }
