"""Transform operational DB CDC JSON records → staging-ready air_quality frame.

Maps simulated OLTP columns to the same canonical schema as UCI processed,
with source_system = 'operational_db'.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

import pandas as pd

from src.ingestion.db_client import SOURCE_IDENTIFIER
from src.processing.dq import apply_data_quality
from src.processing.schema import CANONICAL_OUTPUT_COLUMNS
from src.staging.schema import AIR_COLUMNS

SCHEMA_VERSION = "1.0.0"

# operational_air_quality column → canonical processed name
DB_TO_CANONICAL: dict[str, str] = {
    "station_name": "station_name",
    "pm25": "pm25_ug_m3",
    "pm10": "pm10_ug_m3",
    "so2": "so2_ug_m3",
    "no2": "no2_ug_m3",
    "co": "co_ug_m3",
    "o3": "o3_ug_m3",
    "temp": "temperature_c",
    "pres": "pressure_hpa",
    "dewp": "dew_point_c",
    "rain": "rain_mm",
    "wd": "wind_direction",
    "wspd": "wind_speed_m_s",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def records_to_frame(
    records: Sequence[dict[str, Any]],
    *,
    source_object_key: str,
    source_sha256: str,
    source_file_name: str | None = None,
    process_time: str | None = None,
    source_system: str = SOURCE_IDENTIFIER,
) -> pd.DataFrame:
    """Build a canonical DataFrame (pre-DQ) from one CDC batch payload."""
    if not records:
        return pd.DataFrame(columns=list(CANONICAL_OUTPUT_COLUMNS))

    raw = pd.DataFrame(list(records))
    missing = [c for c in DB_TO_CANONICAL if c not in raw.columns]
    if "event_time_local" not in raw.columns:
        missing.append("event_time_local")
    if missing:
        raise ValueError(f"CDC records missing columns: {missing}")

    out = pd.DataFrame()
    out["event_time_local"] = pd.to_datetime(raw["event_time_local"])
    for src, dst in DB_TO_CANONICAL.items():
        out[dst] = raw[src]

    numeric_cols = [
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
    # No UCI "No" column in operational extract
    out["source_row_no"] = pd.Series([pd.NA] * len(out), dtype="Int64")

    file_name = source_file_name or source_object_key.rsplit("/", 1)[-1]
    out["source_file_name"] = file_name
    out["source_system"] = source_system
    out["source_object_key"] = source_object_key
    out["source_sha256"] = source_sha256
    out["process_time"] = process_time or _utc_now_iso()

    return out.reset_index(drop=True)


def transform_cdc_records(
    records: Sequence[dict[str, Any]],
    *,
    source_object_key: str,
    source_sha256: str,
    source_file_name: str | None = None,
    process_time: str | None = None,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """
    Transform + DQ. Returns clean rows (staging-loadable) and quarantine counts.

    Quarantine (invalid negatives) is not loaded — same policy as UCI staging.
    """
    frame = records_to_frame(
        records,
        source_object_key=source_object_key,
        source_sha256=source_sha256,
        source_file_name=source_file_name,
        process_time=process_time,
    )
    if frame.empty:
        empty = pd.DataFrame(columns=list(AIR_COLUMNS))
        return empty, {
            "input_rows": 0,
            "clean_rows": 0,
            "quarantine_rows": 0,
        }

    dq = apply_data_quality(frame)
    clean = dq.clean.copy()
    # Ensure staging column order / presence
    for col in AIR_COLUMNS:
        if col not in clean.columns:
            clean[col] = pd.NA
    clean = clean.loc[:, list(AIR_COLUMNS)]
    stats = {
        "input_rows": len(frame),
        "clean_rows": len(clean),
        "quarantine_rows": dq.quarantine_row_count,
    }
    return clean, stats
