"""Canonical schema for Open-Meteo processed weather (Phase 5b)."""

from __future__ import annotations

SCHEMA_VERSION = "1.0.0"
SOURCE_SYSTEM = "openmeteo_historical"

# Open-Meteo hourly field → om_* column (DATA_GUIDE §26)
OM_HOURLY_TO_CANONICAL: dict[str, str] = {
    "temperature_2m": "om_temperature_c",
    "dew_point_2m": "om_dew_point_c",
    "surface_pressure": "om_surface_pressure_hpa",
    "rain": "om_rain_mm",
    "wind_speed_10m": "om_wind_speed_m_s",
    "wind_direction_10m": "om_wind_direction_deg",
    "cloud_cover": "om_cloud_cover_pct",
}

LINEAGE_COLUMNS: tuple[str, ...] = (
    "source_object_key",
    "source_system",
    "source_sha256",
    "process_time",
)

CANONICAL_OUTPUT_COLUMNS: tuple[str, ...] = (
    "event_time_local",
    "station_name",
    *OM_HOURLY_TO_CANONICAL.values(),
    *LINEAGE_COLUMNS,
)

NATURAL_KEY_COLUMNS: tuple[str, ...] = ("station_name", "event_time_local")
