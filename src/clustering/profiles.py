"""Phase 9b: build and QC station pollution profiles for clustering."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.clustering.smoke import PROFILE_END, PROFILE_START
from src.eda.db import read_sql

SQL_PATH = (
    Path(__file__).resolve().parents[2]
    / "sql"
    / "clustering"
    / "station_pollution_profile.sql"
)

EXPECTED_STATIONS = 12

# Identity / meta — not fed to KMeans in v1
META_COLS = ("station_key", "station_name", "district", "hour_count", "pm25_hour_count")

# Numeric features intended for StandardScaler + KMeans (P9c)
CLUSTER_FEATURE_COLS = (
    "mean_pm25",
    "median_pm25",
    "std_pm25",
    "mean_pm10",
    "mean_no2",
    "mean_co",
    "mean_so2",
    "mean_o3",
    "mean_pm25_spring",
    "mean_pm25_summer",
    "mean_pm25_autumn",
    "mean_pm25_winter",
    "pct_hours_pm25_ge_75",
    "pct_hours_pm25_ge_115",
    "episode_count",
    "mean_episode_duration_h",
    "total_episode_hours",
)

# Soft sanity vs Phase 8 ranking (full-period means; window is 2013–2016)
EXPECTED_HIGH_PM25 = "Dongsi"
EXPECTED_LOW_PM25 = "Dingling"


def load_profile_sql() -> str:
    """Load profile SQL with PROFILE_START / PROFILE_END injected (single source)."""
    raw = SQL_PATH.read_text(encoding="utf-8")
    return (
        raw.replace("__PROFILE_START__", PROFILE_START).replace(
            "__PROFILE_END__", PROFILE_END
        )
    )


def fetch_station_profiles() -> pd.DataFrame:
    """Run station_pollution_profile.sql against DWH / mart."""
    df = read_sql(load_profile_sql())
    if df.empty:
        return df
    # Stable column order
    ordered = [c for c in list(META_COLS) + list(CLUSTER_FEATURE_COLS) if c in df.columns]
    extra = [c for c in df.columns if c not in ordered]
    return df[ordered + extra]


def qc_station_profiles(df: pd.DataFrame) -> dict[str, Any]:
    """Return QC report; ok=True when grain and soft ranking checks pass."""
    issues: list[str] = []
    n = len(df)
    if n != EXPECTED_STATIONS:
        issues.append(f"expected {EXPECTED_STATIONS} rows, got {n}")

    if "station_key" in df.columns:
        nunique = int(df["station_key"].nunique())
        if nunique != n:
            issues.append(f"duplicate station_key: unique={nunique}, rows={n}")
    else:
        issues.append("missing station_key")

    for col in CLUSTER_FEATURE_COLS:
        if col not in df.columns:
            issues.append(f"missing feature column: {col}")
            continue
        nulls = int(df[col].isna().sum())
        if nulls:
            issues.append(f"{col}: {nulls} nulls")

    ranking_ok = False
    if "station_name" in df.columns and "mean_pm25" in df.columns and not df.empty:
        ranked = df.sort_values("mean_pm25", ascending=False)
        top = str(ranked.iloc[0]["station_name"])
        bottom = str(ranked.iloc[-1]["station_name"])
        ranking_ok = top == EXPECTED_HIGH_PM25 and bottom == EXPECTED_LOW_PM25
        if not ranking_ok:
            issues.append(
                f"ranking soft-check: top={top!r} (want {EXPECTED_HIGH_PM25}), "
                f"bottom={bottom!r} (want {EXPECTED_LOW_PM25})"
            )

    return {
        "ok": len(issues) == 0,
        "row_count": n,
        "station_count": int(df["station_key"].nunique()) if "station_key" in df.columns else 0,
        "profile_window": {"start": PROFILE_START, "end": PROFILE_END},
        "cluster_feature_cols": list(CLUSTER_FEATURE_COLS),
        "meta_cols": list(META_COLS),
        "ranking_soft_ok": ranking_ok,
        "issues": issues,
    }
