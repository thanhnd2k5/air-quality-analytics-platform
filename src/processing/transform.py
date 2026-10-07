"""Transform UCI raw CSV bytes into canonical DataFrame (Phase 4)."""

from __future__ import annotations

import io
from typing import Any

import pandas as pd

from src.processing.schema import (
    REQUIRED_UCI_COLUMNS,
    SOURCE_SYSTEM,
    TIME_PART_COLUMNS,
    UCI_TO_CANONICAL,
)


def transform_uci_csv_bytes(
    data: bytes,
    station: str,
    *,
    source_file_name: str,
    source_object_key: str = "",
    source_sha256: str = "",
    process_time: str,
    source_system: str = SOURCE_SYSTEM,
) -> pd.DataFrame:
    """
    Parse UCI CSV → rename → build event_time_local → cast → attach lineage.

    Does not impute. Does not drop rows. DQ flags are applied separately.
    """
    df = pd.read_csv(io.BytesIO(data), na_values=["NA", "NaN", ""], keep_default_na=True)
    missing = [c for c in REQUIRED_UCI_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required UCI columns for {station}: {missing}")

    for part in TIME_PART_COLUMNS:
        df[part] = pd.to_numeric(df[part], errors="coerce")
    if df[list(TIME_PART_COLUMNS)].isna().any().any():
        raise ValueError(f"Invalid year/month/day/hour values for station {station}")

    df["event_time_local"] = pd.to_datetime(
        {
            "year": df["year"].astype(int),
            "month": df["month"].astype(int),
            "day": df["day"].astype(int),
            "hour": df["hour"].astype(int),
        }
    )

    out = df.rename(columns=UCI_TO_CANONICAL).copy()
    out = out.drop(columns=[c for c in TIME_PART_COLUMNS if c in out.columns])

    # Numeric casts (wind_direction stays string/categorical)
    numeric_cols = [
        "source_row_no",
        "pm25_ug_m3",
        "pm10_ug_m3",
        "so2_ug_m3",
        "no2_ug_m3",
        "co_ug_m3",
        "o3_ug_m3",
        "temperature_c",
        "pressure_hpa",
        "dew_point_c",
        "rain_mm",
        "wind_speed_m_s",
    ]
    for col in numeric_cols:
        out[col] = pd.to_numeric(out[col], errors="coerce")

    out["station_name"] = out["station_name"].astype(str).str.strip()
    out["wind_direction"] = out["wind_direction"].astype("string")

    mismatched = out["station_name"] != station
    if mismatched.any():
        bad = out.loc[mismatched, "station_name"].unique().tolist()
        raise ValueError(
            f"station_name mismatch for expected '{station}': found {bad}"
        )

    out["source_file_name"] = source_file_name
    out["source_system"] = source_system
    out["source_object_key"] = source_object_key
    out["source_sha256"] = source_sha256
    out["process_time"] = process_time

    return out.reset_index(drop=True)


def dataframe_to_parquet_bytes(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    df.to_parquet(buffer, index=False, engine="pyarrow")
    return buffer.getvalue()


def lineage_defaults(**overrides: Any) -> dict[str, Any]:
    base = {
        "source_file_name": "",
        "source_object_key": "",
        "source_sha256": "",
        "source_system": SOURCE_SYSTEM,
    }
    base.update(overrides)
    return base
