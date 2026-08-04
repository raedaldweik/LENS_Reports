"""
Data layer for the RTA Smart Monitoring chatbot.

Two datasets — the exact CSVs the dashboards load:
  - alerts.csv      → operational.html and staff.html (8.5K monitoring alerts)
  - violations.csv  → performance.html (16.5K driver violations with risk scores)

"Now" is anchored to the latest timestamp in each dataset (the dashboards use the
same convention) so period windows like "this week" stay stable over the data.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

# CSV lookup order: explicit env override → repo root (two levels up) → ./data
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_SEARCH_DIRS = [
    Path(os.getenv("DATA_DIR")) if os.getenv("DATA_DIR") else None,
    _BACKEND_DIR.parent.parent,          # repo root when running from chatbot/backend
    _BACKEND_DIR / "data",
]
_REMOTE_BASE = "https://raedaldweik.github.io/reports"  # same URLs the dashboards use

DATASETS = ("alerts", "violations")


def _csv_source(name: str) -> str:
    for d in _SEARCH_DIRS:
        if d and (d / f"{name}.csv").is_file():
            return str(d / f"{name}.csv")
    return f"{_REMOTE_BASE}/{name}.csv"


@lru_cache(maxsize=None)
def _load(dataset: str) -> pd.DataFrame:
    if dataset not in DATASETS:
        raise ValueError(f"unknown dataset: {dataset}")
    df = pd.read_csv(_csv_source(dataset))
    df["_ts"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["_ts"]).reset_index(drop=True)
    if dataset == "alerts":
        df["resolution_hours"] = pd.to_numeric(df["resolution_hours"], errors="coerce")
        df["sla_target_hours"] = pd.to_numeric(df["sla_target_hours"], errors="coerce")
    else:
        df["driver_risk_score"] = pd.to_numeric(df["driver_risk_score"], errors="coerce")
    return df


def data_now(dataset: str = "alerts") -> pd.Timestamp:
    return _load(dataset)["_ts"].max()


def risk_tier(score: float) -> str:
    """Same thresholds performance.html uses."""
    if score >= 8.0:
        return "critical"
    if score >= 6.5:
        return "high"
    if score >= 3.5:
        return "moderate"
    return "low"


# Staff roster — embedded in staff.html, mirrored here verbatim.
OPERATORS = [
    {"id": "OP001", "name": "Ahmed Salem",        "role": "Senior Operator",  "team": "Traffic Operations A", "tier": "excellent"},
    {"id": "OP002", "name": "Khalid Al Suwaidi",  "role": "Operator",         "team": "Traffic Operations A", "tier": "excellent"},
    {"id": "OP003", "name": "Omar Al Falasi",     "role": "Operator",         "team": "Traffic Operations A", "tier": "ontrack"},
    {"id": "OP004", "name": "Mariam Khan",        "role": "Junior Operator",  "team": "Traffic Operations A", "tier": "needs"},
    {"id": "OP005", "name": "John Doe",           "role": "Shift Supervisor", "team": "Traffic Operations B", "tier": "excellent"},
    {"id": "OP006", "name": "Laila Mansour",      "role": "Operator",         "team": "Traffic Operations B", "tier": "ontrack"},
    {"id": "OP007", "name": "Hassan Al Tayer",    "role": "Operator",         "team": "Traffic Operations B", "tier": "ontrack"},
    {"id": "OP008", "name": "Faisal Al Marri",    "role": "Junior Operator",  "team": "Traffic Operations B", "tier": "needs"},
    {"id": "OP009", "name": "Saeed Al Nuaimi",    "role": "Senior Operator",  "team": "Marine Patrol",        "tier": "excellent"},
    {"id": "OP010", "name": "Rashid Al Shamsi",   "role": "Operator",         "team": "Marine Patrol",        "tier": "ontrack"},
    {"id": "OP011", "name": "Sultan Al Awadhi",   "role": "Operator",         "team": "Marine Patrol",        "tier": "ontrack"},
    {"id": "OP012", "name": "Bilal Al Owais",     "role": "Junior Operator",  "team": "Marine Patrol",        "tier": "ontrack"},
    {"id": "OP013", "name": "Tariq Al Hashimi",   "role": "Shift Supervisor", "team": "Public Transit Unit",  "tier": "excellent"},
    {"id": "OP014", "name": "Yousef Al Mazrouei", "role": "Operator",         "team": "Public Transit Unit",  "tier": "ontrack"},
    {"id": "OP015", "name": "Ibrahim Al Naqbi",   "role": "Operator",         "team": "Public Transit Unit",  "tier": "excellent"},
    {"id": "OP016", "name": "Mansour Al Zaabi",   "role": "Junior Operator",  "team": "Public Transit Unit",  "tier": "needs"},
    {"id": "OP017", "name": "Hamad Al Qassimi",   "role": "Senior Operator",  "team": "Smart Enforcement",    "tier": "excellent"},
    {"id": "OP018", "name": "Adel Al Hammadi",    "role": "Operator",         "team": "Smart Enforcement",    "tier": "ontrack"},
    {"id": "OP019", "name": "Marwan Al Mansouri", "role": "Operator",         "team": "Smart Enforcement",    "tier": "ontrack"},
    {"id": "OP020", "name": "Ayman Al Maktoum",   "role": "Junior Operator",  "team": "Smart Enforcement",    "tier": "ontrack"},
    {"id": "OP021", "name": "Walid Al Suwaidi",   "role": "Senior Operator",  "team": "Field Response Team",  "tier": "excellent"},
    {"id": "OP022", "name": "Mahmoud Al Marri",   "role": "Operator",         "team": "Field Response Team",  "tier": "ontrack"},
    {"id": "OP023", "name": "Ziad Al Falasi",     "role": "Operator",         "team": "Field Response Team",  "tier": "needs"},
    {"id": "OP024", "name": "Karim Al Tayer",     "role": "Junior Operator",  "team": "Field Response Team",  "tier": "needs"},
]
TIER_LABELS = {"excellent": "Excellent", "ontrack": "On Track", "needs": "Needs Improvement"}


# ──────────── filtering ────────────

def _apply_filters(df: pd.DataFrame, filters: list[dict] | None) -> pd.DataFrame:
    if not filters:
        return df
    for f in filters:
        col, op, val = f.get("column"), f.get("op", "=="), f.get("value")
        if col not in df.columns:
            raise ValueError(f"unknown column: {col}")
        s = df[col]
        if op == "==":
            df = df[s == val]
        elif op == "!=":
            df = df[s != val]
        elif op in (">", "<", ">=", "<="):
            sn = pd.to_numeric(s, errors="coerce")
            df = df[{">": sn > val, "<": sn < val, ">=": sn >= val, "<=": sn <= val}[op]]
        elif op == "between":
            sn = pd.to_numeric(s, errors="coerce")
            df = df[(sn >= val[0]) & (sn <= val[1])]
        elif op == "contains":
            df = df[s.astype(str).str.contains(str(val), case=False, na=False)]
        elif op == "not_contains":
            df = df[~s.astype(str).str.contains(str(val), case=False, na=False)]
        elif op == "in":
            df = df[s.isin(val if isinstance(val, list) else [val])]
        elif op == "not_in":
            df = df[~s.isin(val if isinstance(val, list) else [val])]
        elif op == "is_null":
            df = df[s.isna()]
        elif op == "not_null":
            df = df[s.notna()]
        else:
            raise ValueError(f"unknown operator: {op}")
    return df


def _window(dataset: str, period_days: int | None) -> pd.DataFrame:
    df = _load(dataset)
    if period_days:
        cutoff = data_now(dataset) - pd.Timedelta(days=period_days)
        df = df[df["_ts"] >= cutoff]
    return df


def get_rows(dataset: str, filters: list[dict] | None = None,
             period_days: int | None = None) -> pd.DataFrame:
    return _apply_filters(_window(dataset, period_days), filters)


def _clean(v: Any) -> Any:
    if hasattr(v, "item"):
        try:
            v = v.item()
        except Exception:
            pass
    if isinstance(v, float):
        return round(v, 3)
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    return v


def _records(df: pd.DataFrame, limit: int = 20) -> list[dict]:
    df = df.drop(columns=[c for c in df.columns if c.startswith("_")], errors="ignore")
    return [{k: _clean(v) for k, v in r.items()} for r in df.head(limit).to_dict("records")]


# ──────────── schema / description ────────────

def describe_dataset(dataset: str) -> dict:
    df = _load(dataset)
    cols = {}
    for c in df.columns:
        if c.startswith("_"):
            continue
        if pd.api.types.is_numeric_dtype(df[c]):
            cols[c] = "numeric"
        else:
            nu = df[c].nunique()
            cols[c] = f"categorical ({nu} values)" if nu <= 30 else "text"
    return {
        "dataset": dataset,
        "rows": len(df),
        "date_range": [str(df['_ts'].min().date()), str(df['_ts'].max().date())],
        "columns": cols,
    }


def describe_column(dataset: str, column: str) -> dict:
    df = _load(dataset)
    if column not in df.columns:
        return {"error": f"unknown column: {column}", "available": [c for c in df.columns if not c.startswith('_')]}
    s = df[column]
    if pd.api.types.is_numeric_dtype(s):
        return {"column": column, "type": "numeric",
                "mean": _clean(s.mean()), "median": _clean(s.median()),
                "min": _clean(s.min()), "max": _clean(s.max()), "std": _clean(s.std())}
    vc = s.value_counts().head(30)
    return {"column": column, "type": "categorical",
            "value_counts": {str(k): int(v) for k, v in vc.items()}}


# ──────────── dashboard KPI bundles ────────────

def performance_kpis(period_days: int | None = None) -> dict:
    """KPI strip of performance.html (violations.csv)."""
    df = _window("violations", period_days)
    drivers = df.sort_values("_ts").drop_duplicates("driver_id", keep="last")
    tiers = drivers["driver_risk_score"].apply(risk_tier)
    return {
        "total_violations": len(df),
        "active_drivers": int((drivers["driver_status"] == "active").sum()),
        "active_vehicles": round((drivers["driver_status"] == "active").sum() * 0.66),
        "drivers_under_investigation": int((drivers["driver_status"] == "investigation").sum()),
        "suspended_drivers": int((drivers["driver_status"] == "suspended").sum()),
        "high_risk_drivers": int(tiers.isin(["critical", "high"]).sum()),
        "avg_driver_risk_score": _clean(drivers["driver_risk_score"].mean()),
        "severity_counts": {str(k): int(v) for k, v in df["severity"].value_counts().items()},
    }


def operational_kpis(period_days: int | None = None) -> dict:
    """KPI strip of operational.html (alerts.csv)."""
    df = _window("alerts", period_days)
    closed = df[df["status"] == "closed"]
    res = closed[closed["resolution_hours"] > 0]["resolution_hours"]
    return {
        "total_alerts": len(df),
        "open_alerts": int((df["status"] != "closed").sum()),
        "closed_alerts": len(closed),
        "avg_resolution_hours": _clean(res.mean()) if len(res) else 0,
        "sla_breaches": int((df["sla_met"] == "no").sum()),
        "sla_compliance_pct": _clean(100 * (df["sla_met"] == "yes").mean()) if len(df) else 0,
        "status_counts": {str(k): int(v) for k, v in df["status"].value_counts().items()},
        "priority_counts": {str(k): int(v) for k, v in df["priority"].value_counts().items()},
    }


def staff_kpis(period_days: int | None = None) -> dict:
    """KPI strip of staff.html (alerts.csv joined to the operator roster)."""
    df = _window("alerts", period_days)
    resolved = df[df["status"].isin(["closed", "fined"])]
    res = resolved[resolved["resolution_hours"] > 0]["resolution_hours"]
    return {
        "total_alerts_handled": len(df),
        "resolved_alerts": len(resolved),
        "resolution_rate_pct": _clean(100 * len(resolved) / len(df)) if len(df) else 0,
        "sla_breaches": int((df["sla_met"] == "no").sum()),
        "avg_resolution_hours": _clean(res.mean()) if len(res) else 0,
        "operators": len(OPERATORS),
        "teams": sorted({o["team"] for o in OPERATORS}),
    }


def operator_metrics(period_days: int | None = None, team: str | None = None,
                     sort_by: str = "total", n: int = 24) -> list[dict]:
    """Per-operator workload/SLA metrics — the same join staff.html computes."""
    df = _window("alerts", period_days)
    out = []
    for op in OPERATORS:
        if team and op["team"].lower() != team.lower():
            continue
        rows = df[df["operator_id"] == op["id"]]
        resolved = rows[rows["status"].isin(["closed", "fined"])]
        res = rows[(rows["status"] == "closed") & (rows["resolution_hours"] > 0)]["resolution_hours"]
        out.append({
            **op, "tier_label": TIER_LABELS[op["tier"]],
            "total": len(rows),
            "resolved": len(resolved),
            "breaches": int((rows["sla_met"] == "no").sum()),
            "avg_resolution_hours": _clean(res.mean()) if len(res) else 0,
            "resolution_rate_pct": _clean(100 * len(resolved) / len(rows)) if len(rows) else 0,
        })
    reverse = sort_by != "avg_resolution_hours"
    out.sort(key=lambda o: o.get(sort_by, 0) or 0, reverse=reverse)
    return out[:n]


# ──────────── generic analytics ────────────

def filter_rows(dataset: str, filters: list[dict] | None = None,
                select_columns: list[str] | None = None,
                aggregate: dict | None = None,
                limit: int = 20, period_days: int | None = None) -> dict:
    df = get_rows(dataset, filters, period_days)
    out: dict[str, Any] = {"matched": len(df)}
    if aggregate and aggregate.get("column"):
        col, func = aggregate["column"], aggregate.get("func", "mean")
        s = pd.to_numeric(df[col], errors="coerce")
        out["aggregate"] = {"column": col, "func": func, "value": _clean(getattr(s, func)())}
    elif select_columns:
        cols = [c for c in select_columns if c in df.columns]
        out["rows"] = _records(df[cols] if cols else df, limit)
    else:
        out["rows"] = _records(df, min(limit, 10))
    return out


def groupby_aggregate(dataset: str, group_by: str, metric: str | None = None,
                      func: str = "count", filters: list[dict] | None = None,
                      top: int = 30, period_days: int | None = None) -> dict:
    df = get_rows(dataset, filters, period_days)
    if group_by not in df.columns:
        return {"error": f"unknown column: {group_by}"}
    if metric and metric in df.columns and func != "count":
        s = df.groupby(group_by)[metric].agg(func).sort_values(ascending=False)
    else:
        s = df.groupby(group_by).size().sort_values(ascending=False)
        metric, func = "rows", "count"
    rows = [{group_by: str(k), f"{func}_{metric}": _clean(v)} for k, v in s.head(top).items()]
    return {"group_by": group_by, "metric": metric, "func": func, "rows": rows}


def top_n(dataset: str, sort_by: str, n: int = 10, ascending: bool = False,
          filters: list[dict] | None = None, select_columns: list[str] | None = None,
          period_days: int | None = None, unique_drivers: bool = False) -> dict:
    df = get_rows(dataset, filters, period_days)
    if sort_by not in df.columns:
        return {"error": f"unknown column: {sort_by}"}
    if unique_drivers and "driver_id" in df.columns:
        counts = df.groupby("driver_id").size()
        df = df.sort_values("_ts").drop_duplicates("driver_id", keep="last").copy()
        df["violation_count"] = df["driver_id"].map(counts)
    df = df.sort_values(sort_by, ascending=ascending)
    cols = [c for c in (select_columns or []) if c in df.columns] or None
    return {"rows": _records(df[cols + ([ "violation_count"] if unique_drivers and cols else [])] if cols else df, n)}


def time_series(dataset: str, period_days: int = 30, freq: str = "D",
                split_by: str | None = None, filters: list[dict] | None = None) -> dict:
    df = get_rows(dataset, filters, period_days)
    df = df.set_index("_ts")
    if split_by and split_by in df.columns:
        pivot = df.groupby([pd.Grouper(freq=freq), split_by]).size().unstack(fill_value=0)
        rows = [{"date": str(idx.date()), **{str(c): int(v) for c, v in r.items()}}
                for idx, r in pivot.iterrows()]
    else:
        counts = df.resample(freq).size()
        rows = [{"date": str(idx.date()), "count": int(v)} for idx, v in counts.items()]
    return {"freq": freq, "rows": rows}


def histogram(dataset: str, column: str, bins: int = 10,
              filters: list[dict] | None = None, period_days: int | None = None) -> dict:
    df = get_rows(dataset, filters, period_days)
    s = pd.to_numeric(df[column], errors="coerce").dropna()
    if s.empty:
        return {"error": f"no numeric data in column: {column}"}
    cut = pd.cut(s, bins=bins)
    rows = [{"bin": f"{iv.left:.1f}–{iv.right:.1f}", "count": int(c)} for iv, c in cut.value_counts().sort_index().items()]
    return {"column": column, "rows": rows}


def correlate(dataset: str, col_a: str, col_b: str) -> dict:
    df = _load(dataset)
    a = pd.to_numeric(df[col_a], errors="coerce")
    b = pd.to_numeric(df[col_b], errors="coerce")
    return {"col_a": col_a, "col_b": col_b, "pearson_r": _clean(a.corr(b)), "n": int(min(a.notna().sum(), b.notna().sum()))}
