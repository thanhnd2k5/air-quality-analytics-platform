-- Phase 6 staging tables. Applied by src/staging (not only on first volume init).
-- Hourly tables mirror processed Parquet 1:1. event_time_local is wall-clock
-- Asia/Shanghai stored as timestamp without time zone.

CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE IF NOT EXISTS staging.load_registry (
    dataset TEXT NOT NULL,
    station_name TEXT NOT NULL,
    source_object_key TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (dataset, station_name)
);

COMMENT ON TABLE staging.load_registry IS
    'Idempotency ledger. station_name=''*'' is the full station_reference batch.';

CREATE TABLE IF NOT EXISTS staging.air_quality_hourly (
    source_row_no BIGINT,
    event_time_local TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    station_name TEXT NOT NULL,
    pm25_ug_m3 DOUBLE PRECISION,
    pm10_ug_m3 DOUBLE PRECISION,
    so2_ug_m3 DOUBLE PRECISION,
    no2_ug_m3 DOUBLE PRECISION,
    co_ug_m3 DOUBLE PRECISION,
    o3_ug_m3 DOUBLE PRECISION,
    temperature_c DOUBLE PRECISION,
    pressure_hpa DOUBLE PRECISION,
    dew_point_c DOUBLE PRECISION,
    rain_mm DOUBLE PRECISION,
    wind_direction TEXT,
    wind_speed_m_s DOUBLE PRECISION,
    has_missing_pollutant BOOLEAN,
    has_missing_weather BOOLEAN,
    suspect_cap BOOLEAN,
    data_quality_status TEXT,
    source_file_name TEXT,
    source_system TEXT,
    source_object_key TEXT,
    source_sha256 TEXT,
    process_time TEXT,
    PRIMARY KEY (station_name, event_time_local)
);

COMMENT ON TABLE staging.air_quality_hourly IS
    '1:1 UCI processed hourly. Grain: station_name + event_time_local. Quarantine rows are not loaded.';

CREATE TABLE IF NOT EXISTS staging.weather_openmeteo_hourly (
    event_time_local TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    station_name TEXT NOT NULL,
    om_temperature_c DOUBLE PRECISION,
    om_dew_point_c DOUBLE PRECISION,
    om_surface_pressure_hpa DOUBLE PRECISION,
    om_rain_mm DOUBLE PRECISION,
    om_wind_speed_m_s DOUBLE PRECISION,
    om_wind_direction_deg DOUBLE PRECISION,
    om_cloud_cover_pct DOUBLE PRECISION,
    source_object_key TEXT,
    source_system TEXT,
    source_sha256 TEXT,
    process_time TEXT,
    PRIMARY KEY (station_name, event_time_local)
);

COMMENT ON TABLE staging.weather_openmeteo_hourly IS
    '1:1 Open-Meteo processed hourly. Grain: station_name + event_time_local.';

CREATE TABLE IF NOT EXISTS staging.station_reference (
    station_id INTEGER PRIMARY KEY,
    station_code TEXT NOT NULL,
    station_name TEXT NOT NULL UNIQUE,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    district TEXT,
    coordinate_status TEXT,
    metadata_source TEXT,
    source_url TEXT,
    district_source TEXT,
    district_source_url TEXT,
    notes TEXT
);

COMMENT ON TABLE staging.station_reference IS
    '1:1 seed data/raw/reference/stations.csv. Full replace per load.';
