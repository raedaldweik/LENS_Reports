"""
Data layer for the Dubai Police Smart Assistant.

Three datasets — the exact CSVs behind the Security Analytics & Forecast Center
dashboards (dangerous drivers):

  - violations  → TRF_DANGEROUS_JOIN_V3.csv    (2,462 traffic violations, 750 dangerous drivers)
  - cases       → TRF_DRIVER_CID_CASES.csv     (1,105 rows: 612 criminal reports + 493 no-report rows)
  - movements   → TRF_DRIVER_MOVEMENTS_V2.csv  (750 rows: border status, vehicles, priors per driver)

All three join on TRAFFIC_NO (رقم الملف المروري) — the 750 dangerous drivers
appear in each dataset. Dates use the SAS DDMONYY:HH:MM:SS format.
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

FILES = {
    "violations": "TRF_DANGEROUS_JOIN_V3.csv",
    "cases": "TRF_DRIVER_CID_CASES.csv",
    "movements": "TRF_DRIVER_MOVEMENTS_V2.csv",
}
DATASETS = tuple(FILES)

DANGER_ORDER = ["low", "medium", "dangerous", "highly dangerous"]
DANGER_AR = {"low": "منخفض", "medium": "متوسط", "dangerous": "خطير", "highly dangerous": "عالي الخطورة"}


def _csv_source(name: str) -> str:
    for d in _SEARCH_DIRS:
        if d and (d / FILES[name]).is_file():
            return str(d / FILES[name])
    raise FileNotFoundError(f"{FILES[name]} not found — set DATA_DIR or place it at the repo root")


def _sas_date(s: pd.Series, fix_future_century: bool = False) -> pd.Series:
    """Parse SAS-style '08DEC25:00:00:00' timestamps."""
    out = pd.to_datetime(s.astype(str).str.strip(), format="%d%b%y:%H:%M:%S", errors="coerce")
    if fix_future_century:
        # 2-digit years: '64' parses as 2064 — birth dates in the future roll back a century
        out = out.where(out.dt.year <= 2035, out - pd.DateOffset(years=100))
    return out


def _clean_str(df: pd.DataFrame) -> pd.DataFrame:
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].astype(str).str.strip().replace({"nan": None, "": None})
    return df


def _traffic_no(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.lstrip("0").replace({"": "0"})


@lru_cache(maxsize=None)
def _load(dataset: str) -> pd.DataFrame:
    if dataset not in DATASETS:
        raise ValueError(f"unknown dataset: {dataset}")
    df = pd.read_csv(_csv_source(dataset), encoding="utf-8-sig")
    df = _clean_str(df)

    if dataset == "violations":
        df = df.rename(columns={
            "Traffic No": "TRAFFIC_NO",
            "عدد المركبات": "VEHICLE_COUNT",
            "المركبات المنتهية": "EXPIRED_VEHICLES",
            "المركبات المحجوزة": "IMPOUNDED_VEHICLES",
            "المركبات المطلوبة": "WANTED_VEHICLES",
            "السوابق الجنائية": "CRIMINAL_PRIORS",
        })
        df["TRAFFIC_NO"] = _traffic_no(df["TRAFFIC_NO"])
        for c in ("OFFENCE_SCORE", "OFFENCE_SCORE_T", "TOTAL_FINE", "VEHICLE_COUNT",
                  "EXPIRED_VEHICLES", "IMPOUNDED_VEHICLES", "WANTED_VEHICLES",
                  "CRIMINAL_PRIORS", "GPS_LATITUDE", "GPS_LONGITUDE", "TOT_CASES"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["_ts"] = _sas_date(df["TICKET_DATE"])
        df["BIRTH_DATE_P"] = _sas_date(df["BIRTH_DATE"], fix_future_century=True)
        df["LAST_TICKET_DATE_P"] = _sas_date(df["LAST_TICKET_DATE"])
        df["LIC_ISSUE_DATE_P"] = _sas_date(df["LIC_ISSUE_DATED"])
        df["LIC_EXPIRY_DATE_P"] = _sas_date(df["LIC_EXPIRY_DATE"])
        anchor = df["_ts"].max()
        df["AGE"] = ((anchor - df["BIRTH_DATE_P"]).dt.days // 365).astype("Int64")
        df["AGE_BAND"] = pd.cut(df["AGE"].astype(float), [0, 24, 39, 54, 120],
                                labels=["18-24", "25-39", "40-54", "55+"]).astype(str)
        df["GENDER_DESC"] = df["GENDER"].astype(str).str.strip().map({"2": "ذكر", "1": "أنثى"})
        df["RISK_SCORE"] = (df["OFFENCE_SCORE"] / 100).round(2)   # per-violation risk 0–1

    elif dataset == "cases":
        df = df.rename(columns={
            "case_date": "CASE_DATE",
            "category": "CASE_CATEGORY",                    # مقلقة / غير مقلقة
            "danger category description": "DANGER_CATEGORY_DESC",
            "driver name": "NAME",
            "driver name A": "NAME_A",
            "crime ADSC": "CRIME",
            "Traffic No": "TRAFFIC_NO",
            "وجود البلاغات الجنائية": "HAS_CRIMINAL_REPORT",  # بلاغ جنائي / بدون البلاغات الجنائية
        })
        df["TRAFFIC_NO"] = _traffic_no(df["TRAFFIC_NO"])
        # ISO timestamps here, not SAS format. Rows with no case keep NaT (driver has no report).
        df["_ts"] = pd.to_datetime(df["CASE_DATE"], errors="coerce")

    else:  # movements — one row per driver
        df = df.rename(columns={
            "رقم الملف المروري": "TRAFFIC_NO",
            "الاسم بالعربي": "NAME_A",
            "الجنسية": "NATIONALITY_A",
            "المركبات الغير منتهية": "ACTIVE_VEHICLES",
            "المركبات المنتهية": "EXPIRED_VEHICLES",
            "المهنة": "OCCUPATION",
            "الرقم الموحد": "UNIFIED_NO",
            "الدخول والخروج": "BORDER_STATUS",
            "تاريخ الدخول والخروج": "LAST_CROSSING_DATE",
            "السوابق": "PRIORS",
            "تحركات المركبات": "VEHICLES_MOVING",
            "عدد المركبات": "VEHICLE_COUNT",
            "لا توجد تحركات": "VEHICLES_IDLE",
        })
        df = df.drop(columns=["عدد المركبات 222"], errors="ignore")
        df["TRAFFIC_NO"] = _traffic_no(df["TRAFFIC_NO"])
        for c in ("ACTIVE_VEHICLES", "EXPIRED_VEHICLES", "VEHICLES_MOVING",
                  "VEHICLE_COUNT", "VEHICLES_IDLE"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
        # Normalise داخل/داخل الدولة → داخل الدولة (same for خارج)
        df["BORDER_STATUS"] = df["BORDER_STATUS"].map(
            lambda v: "داخل الدولة" if v and "داخل" in v else ("خارج الدولة" if v and "خارج" in v else v))
        df["BORDER_STATUS_E"] = df["BORDER_STATUS"].map(
            {"داخل الدولة": "inside_country", "خارج الدولة": "outside_country"})
        df["PRIORS_E"] = df["PRIORS"].map({"توجد": "has_priors", "لاتوجد": "no_priors", "متوفى": "deceased"})
        df["_ts"] = _sas_date(df["LAST_CROSSING_DATE"])

    return df.reset_index(drop=True)


def data_now(dataset: str = "violations") -> pd.Timestamp:
    return _load(dataset)["_ts"].max()


# ──────────── per-driver aggregation (the risk view of violations) ────────────

@lru_cache(maxsize=None)
def _drivers() -> pd.DataFrame:
    """One row per dangerous driver, aggregated from the violations dataset."""
    v = _load("violations")
    agg = v.groupby("TRAFFIC_NO").agg(
        NAME=("NAME", "first"),
        NAME_A=("NAME_A", "first"),
        NATIONALITY=("CNT_DESCRIPTION", "first"),
        NATIONALITY_A=("CNT_DESCRIPTION_A", "first"),
        GENDER_DESC=("GENDER_DESC", "first"),
        AGE=("AGE", "first"),
        AGE_BAND=("AGE_BAND", "first"),
        OCCUPATION_DESC=("OCCUPATION_DESC", "first"),
        SPONSOR_NAME=("SPONSOR_NAME", "first"),
        SPONSOR_NAME_A=("SPONSOR_NAME_A", "first"),
        ORG_NAME=("ORG_NAME", "first"),
        ORG_ACTIVITY=("ORG_ACTIVITY", "first"),
        DANGER_CATEGORY_DESC=("DANGER_CATEGORY_DESC", "first"),
        LIC_TYPE=("LIC_Type", "first"),
        LIC_ISSUED_INSTITUTE=("LIC_ISSUED_INSTITUTE", "first"),
        EXAMINER_NAME=("EXAMINER_NAME", "first"),
        PLATE_EMIRATE=("PLC_EMI_CODE", "first"),
        VEHICLE_COUNT=("VEHICLE_COUNT", "first"),
        EXPIRED_VEHICLES=("EXPIRED_VEHICLES", "first"),
        IMPOUNDED_VEHICLES=("IMPOUNDED_VEHICLES", "first"),
        WANTED_VEHICLES=("WANTED_VEHICLES", "first"),
        CRIMINAL_PRIORS=("CRIMINAL_PRIORS", "first"),
        violation_count=("TICKET_NO", "count"),
        total_fines_aed=("TOTAL_FINE", "sum"),
        avg_offence_score=("OFFENCE_SCORE", "mean"),
        last_violation=("_ts", "max"),
        top_offence_a=("OFFENCE_DESCRIPTION_A", lambda s: s.mode().iat[0] if len(s.mode()) else None),
    ).reset_index()
    agg["RISK_SCORE"] = (agg["avg_offence_score"] / 100).round(2)  # 0–1, matches dashboard gauge
    return agg


def drivers_table() -> pd.DataFrame:
    return _drivers().copy()


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
    if v is pd.NaT or (isinstance(v, float) and pd.isna(v)):
        return None
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
    ts = df["_ts"].dropna()
    return {
        "dataset": dataset,
        "file": FILES[dataset],
        "rows": len(df),
        "date_range": [str(ts.min().date()), str(ts.max().date())] if len(ts) else None,
        "columns": cols,
    }


def describe_column(dataset: str, column: str) -> dict:
    df = _load(dataset)
    if column not in df.columns:
        return {"error": f"unknown column: {column}",
                "available": [c for c in df.columns if not c.startswith("_")]}
    s = df[column]
    if pd.api.types.is_numeric_dtype(s):
        return {"column": column, "type": "numeric",
                "mean": _clean(s.mean()), "median": _clean(s.median()),
                "min": _clean(s.min()), "max": _clean(s.max()), "std": _clean(s.std())}
    vc = s.value_counts().head(30)
    return {"column": column, "type": "categorical",
            "value_counts": {str(k): int(v) for k, v in vc.items()}}


# ──────────── dashboard KPI bundles ────────────

def overview_kpis(period_days: int | None = None) -> dict:
    """KPI strip of the dangerous-drivers overview dashboard (page 1)."""
    df = _window("violations", period_days)
    drv = _drivers()
    if period_days:
        drv = drv[drv["TRAFFIC_NO"].isin(df["TRAFFIC_NO"])]
    top = df["OFFENCE_DESCRIPTION_A"].value_counts().head(10)
    return {
        "total_violations": len(df),
        "total_fines_aed": int(df["TOTAL_FINE"].sum()),
        "dangerous_drivers": int(df["TRAFFIC_NO"].nunique()),
        "avg_risk_score": _clean(df["OFFENCE_SCORE"].mean() / 100),     # gauge: 0.57
        "violations_by_danger_category": {str(k): int(v) for k, v in
                                          df["DANGER_CATEGORY_DESC"].value_counts().items()},
        "drivers_by_danger_category": {str(k): int(v) for k, v in
                                       drv["DANGER_CATEGORY_DESC"].value_counts().items()},
        "top_offences": [{"offence": str(k), "count": int(v)} for k, v in top.items()],
        "violations_by_plate_emirate": {str(k): int(v) for k, v in
                                        df["PLC_EMI_CODE"].value_counts().items()},
    }


def cases_kpis() -> dict:
    """KPI strip of the criminal-reports dashboard (page 3)."""
    df = _load("cases")
    reports = df[df["HAS_CRIMINAL_REPORT"] == "بلاغ جنائي"]
    top = reports["CRIME"].value_counts().head(10)
    return {
        "total_rows": len(df),
        "criminal_reports": len(reports),
        "no_criminal_report": int((df["HAS_CRIMINAL_REPORT"] == "بدون البلاغات الجنائية").sum()),
        "concerning_reports": int((df["CASE_CATEGORY"] == "مقلقة").sum()),
        "non_concerning_reports": int((df["CASE_CATEGORY"] == "غير مقلقة").sum()),
        "drivers_with_reports": int(reports["TRAFFIC_NO"].nunique()),
        "top_charges": [{"charge": str(k), "count": int(v)} for k, v in top.items()],
    }


def movements_kpis() -> dict:
    """KPI strip of the movements dashboard (page 4)."""
    df = _load("movements")
    occ = df["OCCUPATION"].value_counts().head(10)
    nat = df["NATIONALITY_A"].value_counts().head(10)
    return {
        "total_persons": len(df),
        "inside_country": int((df["BORDER_STATUS"] == "داخل الدولة").sum()),
        "outside_country": int((df["BORDER_STATUS"] == "خارج الدولة").sum()),
        "total_vehicles": int(df["VEHICLE_COUNT"].sum()),
        "vehicles_moving": int(df["VEHICLES_MOVING"].sum()),
        "vehicles_idle": int(df["VEHICLES_IDLE"].sum()),
        "priors": {str(k): int(v) for k, v in df["PRIORS"].value_counts().items()},
        "top_occupations": [{"occupation": str(k), "count": int(v)} for k, v in occ.items()],
        "top_nationalities": [{"nationality": str(k), "count": int(v)} for k, v in nat.items()],
    }


# ──────────── driver profile (page 2 — البطاقة التعريفية) ────────────

def driver_profile(identifier: str) -> dict:
    """Full cross-dataset profile by traffic-file number or name (EN/AR)."""
    ident = str(identifier).strip()
    v = _load("violations")

    tn = _traffic_no(pd.Series([ident])).iat[0]
    match = v[v["TRAFFIC_NO"] == tn]
    if match.empty:
        by_name = v[v["NAME"].str.contains(ident, case=False, na=False) |
                    v["NAME_A"].str.contains(ident, case=False, na=False)]
        tns = by_name["TRAFFIC_NO"].unique()
        if len(tns) == 0:
            return {"error": f"no driver found for '{identifier}'",
                    "hint": "search by traffic file number (رقم الملف المروري) or by name in Arabic/English"}
        if len(tns) > 1:
            cands = by_name.drop_duplicates("TRAFFIC_NO")[["TRAFFIC_NO", "NAME", "NAME_A", "DANGER_CATEGORY_DESC"]]
            return {"multiple_matches": _records(cands, 10),
                    "hint": "ask the user which traffic file number they mean"}
        match = v[v["TRAFFIC_NO"] == tns[0]]

    row = match.iloc[0]
    tno = row["TRAFFIC_NO"]

    viols = match.sort_values("_ts", ascending=False)
    cases = _load("cases")
    my_cases = cases[(cases["TRAFFIC_NO"] == tno) & (cases["HAS_CRIMINAL_REPORT"] == "بلاغ جنائي")]
    mv = _load("movements")
    my_mv = mv[mv["TRAFFIC_NO"] == tno]

    profile = {
        "traffic_no": tno,
        "identity": {
            "name": row["NAME"], "name_ar": row["NAME_A"],
            "nationality": row["CNT_DESCRIPTION"], "nationality_ar": row["CNT_DESCRIPTION_A"],
            "gender": row["GENDER_DESC"], "age": _clean(row["AGE"]),
            "occupation": row["OCCUPATION_DESC"],
            "sponsor": row["SPONSOR_NAME"], "sponsor_ar": row["SPONSOR_NAME_A"],
            "organization": row["ORG_NAME"], "org_activity": row["ORG_ACTIVITY"],
            "emirates_id": row["EMIRATES_ID"],
        },
        "license": {
            "number": row["LICENSE_NUMBER"], "type": row["LIC_Type"],
            "source": row["LIC_SOURCE"], "issued_institute": row["LIC_ISSUED_INSTITUTE"],
            "examiner": row["EXAMINER_NAME"],
            "issue_date": _clean(row["LIC_ISSUE_DATE_P"]), "expiry_date": _clean(row["LIC_EXPIRY_DATE_P"]),
            "transferred_emirate": row["LIC_TRANSFERRED_EMIRATE"],
        },
        "risk": {
            "score": _clean(match["OFFENCE_SCORE"].mean() / 100),
            "category": row["DANGER_CATEGORY_DESC"],
            "category_ar": DANGER_AR.get(row["DANGER_CATEGORY_DESC"]),
        },
        "violations": {
            "count": len(viols),
            "total_fines_aed": int(viols["TOTAL_FINE"].sum()),
            "last_violation_date": _clean(viols["_ts"].max()),
            "most_frequent_offence_ar": (viols["OFFENCE_DESCRIPTION_A"].mode().iat[0]
                                         if len(viols) else None),
            "list": _records(viols[["TICKET_NO", "TICKET_DATE", "OFFENCE_DESCRIPTION",
                                    "OFFENCE_DESCRIPTION_A", "TOTAL_FINE", "OFFENCE_SCORE",
                                    "LOCATION_DESC_E", "LOCATION_DESC_A", "NEIGHBORHOOD_E",
                                    "PLATE_NO", "PLC_EMI_CODE"]], 10),
        },
        "vehicles": {
            "total": _clean(row["VEHICLE_COUNT"]),
            "expired": _clean(row["EXPIRED_VEHICLES"]),
            "impounded": _clean(row["IMPOUNDED_VEHICLES"]),
            "wanted": _clean(row["WANTED_VEHICLES"]),
        },
        "criminal_record": {
            "priors_count": _clean(row["CRIMINAL_PRIORS"]),
            "reports_count": len(my_cases),
            "concerning": int((my_cases["CASE_CATEGORY"] == "مقلقة").sum()),
            "reports": _records(my_cases[["CASE_DATE", "CRIME", "CASE_CATEGORY"]], 10),
        },
    }
    if len(my_mv):
        m = my_mv.iloc[0]
        profile["movements"] = {
            "border_status": m["BORDER_STATUS"], "border_status_en": m["BORDER_STATUS_E"],
            "last_crossing_date": _clean(m["_ts"]),
            "priors": m["PRIORS"], "occupation": m["OCCUPATION"],
            "unified_no": m["UNIFIED_NO"],
            "vehicles": {"total": _clean(m["VEHICLE_COUNT"]), "active": _clean(m["ACTIVE_VEHICLES"]),
                         "expired": _clean(m["EXPIRED_VEHICLES"]), "moving": _clean(m["VEHICLES_MOVING"]),
                         "idle": _clean(m["VEHICLES_IDLE"])},
        }
    return profile


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
    if unique_drivers and dataset == "violations":
        df = _drivers()
        if sort_by not in df.columns:
            return {"error": f"unknown column: {sort_by}",
                    "available": list(df.columns)}
        df = df.sort_values(sort_by, ascending=ascending)
        cols = [c for c in (select_columns or []) if c in df.columns] or None
        return {"rows": _records(df[cols] if cols else df, n)}
    df = get_rows(dataset, filters, period_days)
    if sort_by not in df.columns:
        return {"error": f"unknown column: {sort_by}"}
    df = df.sort_values(sort_by, ascending=ascending)
    cols = [c for c in (select_columns or []) if c in df.columns] or None
    return {"rows": _records(df[cols] if cols else df, n)}


_FREQ = {"D": "D", "W": "W", "M": "ME", "Q": "QE", "Y": "YE"}


def time_series(dataset: str, period_days: int | None = None, freq: str = "M",
                split_by: str | None = None, filters: list[dict] | None = None) -> dict:
    df = get_rows(dataset, filters, period_days)
    df = df.dropna(subset=["_ts"]).set_index("_ts")
    f = _FREQ.get(freq, "ME")
    if split_by and split_by in df.columns:
        pivot = df.groupby([pd.Grouper(freq=f), split_by]).size().unstack(fill_value=0)
        rows = [{"date": _label(idx, freq), **{str(c): int(x) for c, x in r.items()}}
                for idx, r in pivot.iterrows()]
    else:
        counts = df.resample(f).size()
        rows = [{"date": _label(idx, freq), "count": int(x)} for idx, x in counts.items()]
    return {"freq": freq, "rows": rows}


def _label(idx: pd.Timestamp, freq: str) -> str:
    if freq == "Q":
        return f"{idx.year} Q{idx.quarter}"
    if freq == "Y":
        return str(idx.year)
    if freq == "M":
        return idx.strftime("%Y-%m")
    return str(idx.date())


def histogram(dataset: str, column: str, bins: int = 10,
              filters: list[dict] | None = None, period_days: int | None = None) -> dict:
    df = get_rows(dataset, filters, period_days)
    s = pd.to_numeric(df[column], errors="coerce").dropna()
    if s.empty:
        return {"error": f"no numeric data in column: {column}"}
    cut = pd.cut(s, bins=bins)
    rows = [{"bin": f"{iv.left:.1f}–{iv.right:.1f}", "count": int(c)}
            for iv, c in cut.value_counts().sort_index().items()]
    return {"column": column, "rows": rows}


def correlate(dataset: str, col_a: str, col_b: str) -> dict:
    df = _load(dataset)
    a = pd.to_numeric(df[col_a], errors="coerce")
    b = pd.to_numeric(df[col_b], errors="coerce")
    return {"col_a": col_a, "col_b": col_b, "pearson_r": _clean(a.corr(b)),
            "n": int(min(a.notna().sum(), b.notna().sum()))}
