"""
The three analytical models surfaced on the Dubai Police dashboards:

  - forecasting   → a faithful port of the dashboard's Data-Driven-Content
                    forecast card (AI_Forecast v1): OLS linear trend on distinct
                    drivers per registration year, partial final year dropped,
                    95% prediction interval, headline rounded to the nearest 100
                    ("~700 by 2030")
  - risk          → driver risk scoring (0–1 = avg OFFENCE_SCORE/100; gauge shows 0.57)
  - segmentation  → the Sankey panel (danger category × age band × nationality ×
                    gender × vehicle class profiles)

The risk model also exposes a cross-dataset `watchlist` view: highly-dangerous
drivers with concerning criminal reports who are currently inside the country.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from services import data

# ──────────── Forecasting model (dashboard AI panel, DDC AI_Forecast v1) ────────────
# Same engine as the dashboard's Data-Driven Content card:
#   series  = Distinct(Traffic No) per created_year (registration year)
#   model   = ordinary least squares linear trend, the final (partial) year dropped
#   band    = ŷ ± t(α/2, n−2) · s · sqrt(1 + 1/n + (x−x̄)²/Σ(x−x̄)²)   (95% PREDICTION interval)
#   {fc}    = prediction rounded to the nearest 100  →  "نحو 700 بحلول 2030"
# It is a linear trend, not SAS VA's ARIMA/ESM forecast object — same as the dashboard.

# two-tailed t critical values by degrees of freedom (mirrors the DDC's table)
_TT = {
    80: {1: 3.078, 2: 1.886, 3: 1.638, 4: 1.533, 5: 1.476, 6: 1.440, 7: 1.415,
         8: 1.397, 9: 1.383, 10: 1.372, "inf": 1.282},
    90: {1: 6.314, 2: 2.920, 3: 2.353, 4: 2.132, 5: 2.015, 6: 1.943, 7: 1.895,
         8: 1.860, 9: 1.833, 10: 1.812, "inf": 1.645},
    95: {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
         8: 2.306, 9: 2.262, 10: 2.228, "inf": 1.960},
    99: {1: 63.657, 2: 9.925, 3: 5.841, 4: 4.604, 5: 4.032, 6: 3.707, 7: 3.499,
         8: 3.355, 9: 3.250, 10: 3.169, "inf": 2.576},
}


def _tcrit(conf: int, df: int) -> float:
    row = _TT.get(conf, _TT[95])
    if df <= 0:
        return row[1]
    return row.get(df, row["inf"])


def forecast_dangerous_drivers(horizon_year: int = 2030, confidence: int = 95,
                               drop_partial_year: bool = True) -> dict[str, Any]:
    v = data._load("violations")
    created = v.dropna(subset=["CREATED_DATE_P"])
    yearly = created.groupby(created["CREATED_DATE_P"].dt.year)["TRAFFIC_NO"].nunique().sort_index()
    years = yearly.index.astype(int).tolist()
    counts = yearly.values.astype(float)

    # the dashboard narrative's {now}: drivers on the risk list summed across years
    now_total = int(counts.sum())
    # {pct}: share of that list in danger categories >= 3 (dangerous / highly dangerous)
    dcat = pd.to_numeric(created["DANGER_CATEGORY"], errors="coerce")
    hi = (created.assign(_dc=dcat)
          .groupby([created["CREATED_DATE_P"].dt.year, "_dc"])["TRAFFIC_NO"].nunique())
    hi_total = int(hi[hi.index.get_level_values(1) >= 3].sum())
    hi_pct = round(hi_total / now_total * 100, 1) if now_total else 0.0

    # drop the partial final year — it drags the slope down (the DDC's ?dropLast)
    dropped = None
    fit_years, fit_counts = years, counts
    if drop_partial_year and len(years) > 2:
        dropped = {"year": years[-1], "drivers": int(counts[-1]),
                   "note": "partial year — excluded from the trend fit"}
        fit_years, fit_counts = years[:-1], counts[:-1]

    # OLS linear trend with a proper prediction interval (the DDC's fitTrend)
    xs = np.array(fit_years, float)
    ys = np.array(fit_counts, float)
    n = len(xs)
    mx, my = xs.mean(), ys.mean()
    sxx = float(((xs - mx) ** 2).sum())
    b = float(((xs - mx) * (ys - my)).sum() / sxx)
    a = float(my - b * mx)
    sse = float(((ys - (a + b * xs)) ** 2).sum())
    s = math.sqrt(sse / (n - 2)) if n > 2 else 0.0
    confidence = confidence if confidence in _TT else 95
    t = _tcrit(confidence, n - 2)

    last_fit_year = fit_years[-1]
    horizon_year = max(last_fit_year + 1, min(int(horizon_year or 2030), last_fit_year + 15))

    rows = [{"year": int(y), "drivers": int(c), "type": "actual"} for y, c in zip(years, counts)]
    if dropped:
        rows[-1]["type"] = "actual (partial, not fitted)"
    for y in range(last_fit_year + 1, horizon_year + 1):
        pred = a + b * y
        half = t * s * math.sqrt(1 + 1 / n + (y - mx) ** 2 / sxx)
        rows.append({"year": y, "drivers": round(pred), "type": "forecast",
                     "lower_bound": round(max(0.0, pred - half)), "upper_bound": round(pred + half)})

    final_pred = a + b * horizon_year
    headline_val = round(final_pred / 100) * 100  # the DDC rounds {fc} to the nearest 100
    return {
        "model": "dangerous_drivers_forecast",
        "engine": "dashboard DDC 'AI_Forecast v1' (OLS linear trend + prediction interval)",
        "horizon_year": horizon_year,
        "confidence_pct": confidence,
        "history_years": f"{years[0]}–{years[-1]}",
        "dropped_partial_year": dropped,
        "rows": rows,
        "insights": {
            "drivers_on_risk_list": now_total,          # dashboard {now}: 1,767
            "high_risk_share_pct": hi_pct,              # dashboard {pct}: 53.5
            "forecast_exact": round(final_pred, 1),
            "forecast_headline": headline_val,          # dashboard {fc}: ~700
            "annual_trend_drivers": round(b, 1),        # dashboard {slope}
            "prediction_interval_final": [rows[-1]["lower_bound"], rows[-1]["upper_bound"]],
            "headline": (f"The forecast points to ~{headline_val} dangerous drivers by "
                         f"{horizon_year} (exact prediction {final_pred:.0f}, {confidence}% "
                         f"prediction interval {rows[-1]['lower_bound']}–{rows[-1]['upper_bound']})."),
            "headline_ar": (f"يشير التنبؤ إلى بلوغ العدد نحو {headline_val} بحلول {horizon_year}."),
        },
        "methodology": ("Identical to the dashboard's forecast card: distinct drivers per "
                        "registration year (CREATED_DATE), ordinary-least-squares linear trend "
                        "with the partial final year excluded from the fit, and a "
                        f"{confidence}% prediction interval "
                        "band = ŷ ± t(α/2, n−2)·s·√(1 + 1/n + (x−x̄)²/Σ(x−x̄)²). "
                        "A linear trend, not SAS VA's ARIMA forecast object."),
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
