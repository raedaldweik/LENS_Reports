"""
The three analytical models surfaced on the Dubai Police dashboards:

  - forecasting   → the AI panel's dangerous-driver forecast (2022–2030, ~700 by 2030)
  - risk          → driver risk scoring (0–1 = avg OFFENCE_SCORE/100; gauge shows 0.57)
  - segmentation  → the Sankey panel (danger category × age band × nationality ×
                    gender × vehicle class profiles)

The risk model also exposes a cross-dataset `watchlist` view: highly-dangerous
drivers with concerning criminal reports who are currently inside the country.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from services import data

# ──────────── Forecasting model (dashboard page 1) ────────────
# Distinct dangerous drivers active per year, projected with a dampened linear
# trend — matching the dashboard's AI-narrative forecast of ~700 by 2030.

_DAMPING = 0.7
_BAND = 0.12  # ±12% confidence band


def forecast_dangerous_drivers(horizon_year: int = 2030) -> dict[str, Any]:
    v = data._load("violations").dropna(subset=["_ts"])
    yearly = v.groupby(v["_ts"].dt.year)["TRAFFIC_NO"].nunique().sort_index()
    years = yearly.index.astype(int).tolist()
    counts = yearly.values.astype(float)

    slope = float(np.polyfit(years, counts, 1)[0])
    last_year, last_count = years[-1], float(counts[-1])
    horizon_year = max(last_year + 1, min(int(horizon_year or 2030), last_year + 15))

    rows = [{"year": int(y), "drivers": int(c), "type": "actual"} for y, c in zip(years, counts)]
    value, step = last_count, slope
    for y in range(last_year + 1, horizon_year + 1):
        step *= _DAMPING
        value += step
        rows.append({
            "year": y, "drivers": round(value), "type": "forecast",
            "lower_bound": round(value * (1 - _BAND)),
            "upper_bound": round(value * (1 + _BAND)),
        })

    final = rows[-1]["drivers"]
    growth = (final - last_count) / last_count * 100 if last_count else 0
    return {
        "model": "dangerous_drivers_forecast",
        "horizon_year": horizon_year,
        "history_years": f"{years[0]}–{last_year}",
        "rows": rows,
        "insights": {
            "current_year_drivers": int(last_count),
            "forecast_final": final,
            "growth_pct_vs_current": round(growth, 1),
            "annual_trend_drivers": round(slope, 1),
            "headline": (f"The number of active dangerous drivers is projected to reach "
                         f"~{final} by {horizon_year} (from {int(last_count)} in {last_year})."),
            "confidence": "95%",
        },
        "methodology": ("Distinct dangerous drivers with violations per year (from TICKET_DATE), "
                        f"linear trend dampened at {_DAMPING}/yr, ±{int(_BAND*100)}% confidence band. "
                        "Matches the dashboard AI-narrative forecast (~700 by 2030)."),
    }


# ──────────── Risk model (0–1 scoring) ────────────

RISK_GROUPS = ("NATIONALITY", "OCCUPATION_DESC", "SPONSOR_NAME", "ORG_NAME",
               "ORG_ACTIVITY", "LIC_ISSUED_INSTITUTE", "LIC_TYPE", "GENDER_DESC",
               "AGE_BAND", "PLATE_EMIRATE", "DANGER_CATEGORY_DESC")


def risk_model(view: str = "summary", n: int = 10,
               group_by: str | None = None) -> dict[str, Any]:
    drv = data.drivers_table()

    if view == "top_drivers":
        cols = ["TRAFFIC_NO", "NAME", "NAME_A", "NATIONALITY", "DANGER_CATEGORY_DESC",
                "RISK_SCORE", "violation_count", "total_fines_aed", "CRIMINAL_PRIORS",
                "OCCUPATION_DESC", "SPONSOR_NAME"]
        rows = drv.sort_values(["RISK_SCORE", "violation_count"], ascending=False).head(n)[cols]
        return {"model": "driver_risk", "view": view,
                "rows": [{k: data._clean(v) for k, v in r.items()} for r in rows.to_dict("records")]}

    if view == "by_group":
        col = group_by if group_by in RISK_GROUPS else "NATIONALITY"
        g = drv.groupby(col).agg(
            drivers=("TRAFFIC_NO", "count"),
            avg_risk_score=("RISK_SCORE", "mean"),
            high_risk_drivers=("DANGER_CATEGORY_DESC",
                               lambda s: int(s.isin(["dangerous", "highly dangerous"]).sum())),
            total_fines_aed=("total_fines_aed", "sum"),
        ).sort_values("avg_risk_score", ascending=False)
        rows = [{col: str(k), "drivers": int(r["drivers"]),
                 "avg_risk_score": round(float(r["avg_risk_score"]), 2),
                 "high_risk_drivers": int(r["high_risk_drivers"]),
                 "total_fines_aed": int(r["total_fines_aed"])} for k, r in g.iterrows()]
        return {"model": "driver_risk", "view": view, "group_by": col, "rows": rows[:30]}

    if view == "watchlist":
        return _watchlist(n)

    # default: summary / distribution — matches the dashboard donut + gauge
    cats = drv["DANGER_CATEGORY_DESC"].value_counts()
    v = data._load("violations")
    return {
        "model": "driver_risk", "view": "summary",
        "scoring": "risk score 0–1 = average OFFENCE_SCORE of the driver's violations ÷ 100",
        "total_drivers": len(drv),
        "avg_risk_score_all_drivers": round(float(v["OFFENCE_SCORE"].mean()) / 100, 2),  # gauge 0.57
        "driver_distribution": {c: int(cats.get(c, 0)) for c in
                                ("highly dangerous", "dangerous", "medium", "low")},
        "violations_by_category": {str(k): int(x) for k, x in
                                   v["DANGER_CATEGORY_DESC"].value_counts().items()},
        "avg_score_by_category": {str(k): round(float(x), 2) for k, x in
                                  drv.groupby("DANGER_CATEGORY_DESC")["RISK_SCORE"].mean().items()},
    }


def _watchlist(n: int = 10) -> dict[str, Any]:
    """Priority watchlist: dangerous/highly-dangerous drivers with concerning
    criminal reports, cross-referenced with border status."""
    drv = data.drivers_table()
    cases = data._load("cases")
    mv = data._load("movements")

    concerning = (cases[cases["CASE_CATEGORY"] == "مقلقة"]
                  .groupby("TRAFFIC_NO").size().rename("concerning_reports"))
    out = drv.merge(concerning, on="TRAFFIC_NO", how="left")
    out["concerning_reports"] = out["concerning_reports"].fillna(0).astype(int)
    out = out.merge(mv[["TRAFFIC_NO", "BORDER_STATUS", "PRIORS"]], on="TRAFFIC_NO", how="left")

    hot = out[(out["DANGER_CATEGORY_DESC"].isin(["dangerous", "highly dangerous"]))
              & (out["concerning_reports"] > 0)]
    inside = hot[hot["BORDER_STATUS"] == "داخل الدولة"]
    ranked = inside.sort_values(["concerning_reports", "RISK_SCORE"], ascending=False)

    cols = ["TRAFFIC_NO", "NAME", "NAME_A", "DANGER_CATEGORY_DESC", "RISK_SCORE",
            "concerning_reports", "violation_count", "total_fines_aed",
            "BORDER_STATUS", "PRIORS", "NATIONALITY", "OCCUPATION_DESC"]
    return {
        "model": "driver_risk", "view": "watchlist",
        "criteria": ("danger category ∈ {dangerous, highly dangerous} AND has concerning "
                     "(مقلقة) criminal reports AND currently inside the country"),
        "matching_drivers_inside_country": len(inside),
        "matching_drivers_total": len(hot),
        "rows": [{k: data._clean(v) for k, v in r.items()}
                 for r in ranked.head(n)[cols].to_dict("records")],
    }


# ──────────── Segmentation model (the Sankey panel) ────────────

_SEG_DIMS = {"AGE_BAND": "age band", "NATIONALITY": "nationality", "GENDER_DESC": "gender",
             "LIC_TYPE": "vehicle/licence class", "OCCUPATION_DESC": "occupation",
             "ORG_ACTIVITY": "organization activity", "SPONSOR_NAME": "sponsor"}


def segmentation(dimension: str | None = None, n: int = 5) -> dict[str, Any]:
    drv = data.drivers_table()
    dims = [dimension] if dimension in _SEG_DIMS else list(_SEG_DIMS)[:4]

    categories = {}
    for cat, sub in drv.groupby("DANGER_CATEGORY_DESC"):
        prof = {}
        for d in dims:
            vc = sub[d].value_counts(normalize=True).head(n)
            prof[d] = [{"value": str(k), "share_pct": round(float(x) * 100, 1)} for k, x in vc.items()]
        dominant = " · ".join(f"{prof[d][0]['value']} ({prof[d][0]['share_pct']}%)"
                              for d in dims if prof.get(d))
        categories[str(cat)] = {"drivers": len(sub), "dominant_segment": dominant, "profile": prof}

    ordered = {c: categories[c] for c in
               ("highly dangerous", "dangerous", "medium", "low") if c in categories}
    return {
        "model": "driver_segmentation",
        "dimensions": dims,
        "by_danger_category": ordered,
        "methodology": ("Per danger category, the distribution of drivers across profile "
                        "dimensions (the dashboard's Sankey: category × age × nationality × "
                        "gender × vehicle class)."),
    }
