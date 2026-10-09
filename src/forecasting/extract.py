"""Extract hourly fact + calendar + cluster for forecasting features."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.eda.db import read_sql
from src.forecasting.constants import ML_END, ML_START

SQL_PATH = (
    Path(__file__).resolve().parents[2]
    / "sql"
    / "forecasting"
    / "extract_forecast_base.sql"
)


def fetch_forecast_base(
    *,
    start: str = ML_START,
    end: str = ML_END,
) -> pd.DataFrame:
    """Load station-hour rows with calendar and cluster_id (read-only)."""
    sql = SQL_PATH.read_text(encoding="utf-8")
    df = read_sql(sql, {"start": start, "end": end})
    if df.empty:
        return df
    df["event_time_local"] = pd.to_datetime(df["event_time_local"])
    return df.sort_values(["station_key", "event_time_local"]).reset_index(drop=True)
