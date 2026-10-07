"""Staging table contracts and pure helpers (Phase 6)."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.processing.openmeteo_schema import CANONICAL_OUTPUT_COLUMNS as OM_COLUMNS
from src.processing.schema import CANONICAL_OUTPUT_COLUMNS as UCI_COLUMNS

DATASET_AIR = "air_quality_hourly"
DATASET_OM = "weather_openmeteo_hourly"
DATASET_REFERENCE = "station_reference"

REFERENCE_REGISTRY_STATION = "*"
STATION_REFERENCE_SCHEMA_VERSION = "1.0.0"

UCI_PROCESSED_PREFIX = "processed/uci/air_quality/station={station}/"
OM_PROCESSED_PREFIX = "processed/weather/openmeteo/station={station}/"

TABLE_AIR = "staging.air_quality_hourly"
TABLE_OM = "staging.weather_openmeteo_hourly"
TABLE_REFERENCE = "staging.station_reference"
TABLE_REGISTRY = "staging.load_registry"

# Full UCI timeline (Decision Gate P1-40). Used when a station slice is complete.
EXPECTED_ROW_COUNT = 35064
EXPECTED_START = "2013-03-01 00:00:00"
EXPECTED_END = "2017-02-28 23:00:00"
EXPECTED_STATION_COUNT = 12

STATION_REFERENCE_COLUMNS: tuple[str, ...] = (
    "station_id",
    "station_code",
    "station_name",
    "latitude",
    "longitude",
    "district",
    "coordinate_status",
    "metadata_source",
    "source_url",
    "district_source",
    "district_source_url",
    "notes",
)

_PROCESS_DATE_RE = re.compile(r"process_date=(\d{4}-\d{2}-\d{2})")

# information_schema.data_type values
AIR_COLUMN_TYPES: dict[str, str] = {
    "source_row_no": "bigint",
    "event_time_local": "timestamp without time zone",
    "station_name": "text",
    "pm25_ug_m3": "double precision",
    "pm10_ug_m3": "double precision",
    "so2_ug_m3": "double precision",
    "no2_ug_m3": "double precision",
    "co_ug_m3": "double precision",
    "o3_ug_m3": "double precision",
    "temperature_c": "double precision",
    "pressure_hpa": "double precision",
    "dew_point_c": "double precision",
    "rain_mm": "double precision",
    "wind_direction": "text",
    "wind_speed_m_s": "double precision",
    "has_missing_pollutant": "boolean",
    "has_missing_weather": "boolean",
    "suspect_cap": "boolean",
    "data_quality_status": "text",
    "source_file_name": "text",
    "source_system": "text",
    "source_object_key": "text",
    "source_sha256": "text",
    "process_time": "text",
}

OM_COLUMN_TYPES: dict[str, str] = {
    "event_time_local": "timestamp without time zone",
    "station_name": "text",
    "om_temperature_c": "double precision",
    "om_dew_point_c": "double precision",
    "om_surface_pressure_hpa": "double precision",
    "om_rain_mm": "double precision",
    "om_wind_speed_m_s": "double precision",
    "om_wind_direction_deg": "double precision",
    "om_cloud_cover_pct": "double precision",
    "source_object_key": "text",
    "source_system": "text",
    "source_sha256": "text",
    "process_time": "text",
}

REFERENCE_COLUMN_TYPES: dict[str, str] = {
    "station_id": "integer",
    "station_code": "text",
    "station_name": "text",
    "latitude": "double precision",
    "longitude": "double precision",
    "district": "text",
    "coordinate_status": "text",
    "metadata_source": "text",
    "source_url": "text",
    "district_source": "text",
    "district_source_url": "text",
    "notes": "text",
}


@dataclass(frozen=True)
class RegistryRow:
    source_object_key: str
    source_sha256: str
    schema_version: str
    row_count: int


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def ddl_path() -> Path:
    import os

    env = os.getenv("STAGING_DDL_PATH")
    if env:
        return Path(env)
    candidates = [
        repo_root() / "config" / "postgres" / "ddl" / "staging.sql",
        Path("/opt/airflow/config/postgres/ddl/staging.sql"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def registry_matches(
    existing: RegistryRow | None,
    *,
    source_sha256: str,
    schema_version: str,
    row_count: int,
) -> bool:
    if existing is None:
        return False
    return (
        existing.source_sha256 == source_sha256
        and existing.schema_version == schema_version
        and int(existing.row_count) == int(row_count)
    )


def assert_loadable_object_key(object_key: str) -> None:
    """Staging reads canonical processed objects only, never quarantine."""
    normalized = object_key.replace("\\", "/")
    if "/quarantine/" in f"/{normalized}":
        raise ValueError(f"Refusing to load quarantine object into staging: {object_key}")


def select_latest_processed_key(object_names: list[str]) -> str:
    """Latest process_date Parquet. Quarantine keys and sidecars are ignored."""
    parquets: list[str] = []
    for name in object_names:
        normalized = name.replace("\\", "/")
        if "/quarantine/" in f"/{normalized}":
            continue
        if not normalized.endswith(".parquet"):
            continue
        parquets.append(name)
    if not parquets:
        raise FileNotFoundError("No processed Parquet objects in the given list")

    def sort_key(object_name: str) -> tuple[str, str]:
        match = _PROCESS_DATE_RE.search(object_name)
        day = match.group(1) if match else ""
        return (day, object_name)

    return sorted(parquets, key=sort_key)[-1]


def meta_key_for(parquet_key: str) -> str:
    if parquet_key.endswith(".parquet"):
        return parquet_key[: -len(".parquet")] + ".meta.json"
    return f"{parquet_key}.meta.json"


def require_sidecar_fields(sidecar: dict) -> tuple[str, str, int]:
    missing = [name for name in ("source_sha256", "schema_version", "row_count") if name not in sidecar]
    if missing:
        raise ValueError(f"Processed sidecar missing fields: {missing}")
    return str(sidecar["source_sha256"]), str(sidecar["schema_version"]), int(sidecar["row_count"])


def assert_frame_ready(df: pd.DataFrame, *, station: str, columns: tuple[str, ...], row_count: int) -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise ValueError(f"Processed Parquet missing columns: {missing}")
    if len(df) != int(row_count):
        raise RuntimeError(
            f"Parquet row count {len(df)} != sidecar row_count {row_count} for station {station}"
        )
    if df.duplicated(subset=["station_name", "event_time_local"]).any():
        raise RuntimeError(f"Duplicate natural key in processed Parquet for station {station}")
    stations = set(df["station_name"].astype(str).unique())
    if stations != {station}:
        raise RuntimeError(f"station_name mismatch for '{station}': found {sorted(stations)}")


def frame_to_copy_buffer(df: pd.DataFrame, columns: tuple[str, ...] | list[str]) -> io.StringIO:
    """CSV buffer for COPY ... NULL ''. Empty cells become SQL NULL."""
    out = df.loc[:, list(columns)].copy()
    for col in out.columns:
        series = out[col]
        if pd.api.types.is_datetime64_any_dtype(series):
            out[col] = series.dt.strftime("%Y-%m-%d %H:%M:%S")
            continue
        dtype_name = str(series.dtype)
        if pd.api.types.is_bool_dtype(series) or dtype_name == "boolean":
            out[col] = [
                "" if pd.isna(value) else ("true" if bool(value) else "false") for value in series
            ]
            continue
        if col in {"source_row_no", "station_id"}:
            out[col] = ["" if pd.isna(value) else str(int(value)) for value in series]
    buffer = io.StringIO()
    out.to_csv(buffer, index=False, header=False, na_rep="")
    buffer.seek(0)
    return buffer


def copy_sql(table: str, columns: tuple[str, ...] | list[str]) -> str:
    column_list = ", ".join(columns)
    return f"COPY {table} ({column_list}) FROM STDIN WITH (FORMAT csv, NULL '')"


# Re-export canonical column tuples so loaders do not import two schemas ad hoc.
AIR_COLUMNS = UCI_COLUMNS
OM_COLUMNS_OUT = OM_COLUMNS
