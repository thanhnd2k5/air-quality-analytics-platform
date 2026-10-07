"""Canonical schema + DQ constants for UCI processed layer (Phase 4)."""

from __future__ import annotations

SCHEMA_VERSION = "1.0.0"
SOURCE_SYSTEM = "uci_prsa"

# UCI source columns that collapse into event_time_local
TIME_PART_COLUMNS: tuple[str, ...] = ("year", "month", "day", "hour")

# Direct renames (excludes year/month/day/hour)
UCI_TO_CANONICAL: dict[str, str] = {
    "No": "source_row_no",
    "PM2.5": "pm25_ug_m3",
    "PM10": "pm10_ug_m3",
    "SO2": "so2_ug_m3",
    "NO2": "no2_ug_m3",
    "CO": "co_ug_m3",
    "O3": "o3_ug_m3",
    "TEMP": "temperature_c",
    "PRES": "pressure_hpa",
    "DEWP": "dew_point_c",
    "RAIN": "rain_mm",
    "wd": "wind_direction",
    "WSPM": "wind_speed_m_s",
    "station": "station_name",
}

REQUIRED_UCI_COLUMNS: tuple[str, ...] = (
    "No",
    "year",
    "month",
    "day",
    "hour",
    "PM2.5",
    "PM10",
    "SO2",
    "NO2",
    "CO",
    "O3",
    "TEMP",
    "PRES",
    "DEWP",
    "RAIN",
    "wd",
    "WSPM",
    "station",
)

POLLUTANT_COLUMNS: tuple[str, ...] = (
    "pm25_ug_m3",
    "pm10_ug_m3",
    "so2_ug_m3",
    "no2_ug_m3",
    "co_ug_m3",
    "o3_ug_m3",
)

WEATHER_COLUMNS: tuple[str, ...] = (
    "temperature_c",
    "pressure_hpa",
    "dew_point_c",
    "rain_mm",
    "wind_direction",
    "wind_speed_m_s",
)

# Must be >= 0 when present (TEMP/DEWP may be negative)
NON_NEGATIVE_COLUMNS: tuple[str, ...] = (
    "pm25_ug_m3",
    "pm10_ug_m3",
    "so2_ug_m3",
    "no2_ug_m3",
    "co_ug_m3",
    "o3_ug_m3",
    "rain_mm",
    "wind_speed_m_s",
)

# Round ceiling values flagged as SUSPECT_CAP (DATA_GUIDE §16 / P1-44)
SUSPECT_CAP_VALUES: dict[str, frozenset[float]] = {
    "pm25_ug_m3": frozenset({999.0}),
    "pm10_ug_m3": frozenset({999.0}),
    "co_ug_m3": frozenset({10000.0}),
}

DQ_FLAG_COLUMNS: tuple[str, ...] = (
    "has_missing_pollutant",
    "has_missing_weather",
    "suspect_cap",
    "data_quality_status",
)

LINEAGE_COLUMNS: tuple[str, ...] = (
    "source_file_name",
    "source_system",
    "source_object_key",
    "source_sha256",
    "process_time",
)

# Final column order for processed Parquet (measure + DQ + lineage)
CANONICAL_OUTPUT_COLUMNS: tuple[str, ...] = (
    "source_row_no",
    "event_time_local",
    "station_name",
    *POLLUTANT_COLUMNS,
    *WEATHER_COLUMNS,
    *DQ_FLAG_COLUMNS,
    *LINEAGE_COLUMNS,
)

NATURAL_KEY_COLUMNS: tuple[str, ...] = ("station_name", "event_time_local")
