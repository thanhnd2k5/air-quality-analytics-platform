"""Unit tests for Open-Meteo client + transform (Phase 5)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.ingestion.openmeteo_client import hourly_to_records
from src.ingestion.openmeteo_to_minio import iter_date_chunks, request_fingerprint
from src.processing.openmeteo_to_processed import transform_openmeteo_json_bytes
from src.reference.stations import get_station, load_stations


FIXTURE = {
    "latitude": 39.89,
    "longitude": 116.36,
    "timezone": "Asia/Shanghai",
    "hourly_units": {
        "time": "iso8601",
        "temperature_2m": "°C",
        "cloud_cover": "%",
    },
    "hourly": {
        "time": ["2015-01-01T00:00", "2015-01-01T01:00"],
        "temperature_2m": [1.0, 2.0],
        "dew_point_2m": [-5.0, -4.0],
        "rain": [0.0, 0.0],
        "wind_speed_10m": [1.5, 2.0],
        "wind_direction_10m": [90.0, 100.0],
        "surface_pressure": [1020.0, 1019.0],
        "cloud_cover": [10.0, 20.0],
    },
}


def test_load_stations_has_wanshouxigong():
    stations = load_stations()
    assert "Wanshouxigong" in stations
    ref = get_station("Wanshouxigong")
    assert ref.latitude == 39.878
    assert ref.longitude == 116.352
    assert ref.coordinate_status == "LITERATURE"


def test_iter_date_chunks_yearly():
    chunks = iter_date_chunks("2013-03-01", "2017-02-28", chunk_months=12)
    assert chunks[0] == ("2013-03-01", "2013-12-31")
    assert chunks[-1] == ("2017-01-01", "2017-02-28")
    assert len(chunks) == 5


def test_request_fingerprint_stable():
    a = request_fingerprint(
        station="Wanshouxigong",
        latitude=39.878,
        longitude=116.352,
        start_date="2015-01-01",
        end_date="2015-01-31",
        timezone="Asia/Shanghai",
        hourly=("temperature_2m", "cloud_cover"),
    )
    b = request_fingerprint(
        station="Wanshouxigong",
        latitude=39.878,
        longitude=116.352,
        start_date="2015-01-01",
        end_date="2015-01-31",
        timezone="Asia/Shanghai",
        hourly=("temperature_2m", "cloud_cover"),
    )
    assert a == b
    assert len(a) == 64


def test_hourly_to_records_and_transform():
    rows = hourly_to_records(FIXTURE)
    assert len(rows) == 2
    assert rows[0]["cloud_cover"] == 10.0

    raw = json.dumps(FIXTURE).encode("utf-8")
    df = transform_openmeteo_json_bytes(
        raw,
        "Wanshouxigong",
        source_object_key="raw/test.json",
        source_sha256="abc",
        process_time="2026-10-07T00:00:00Z",
    )
    assert list(df.columns)[0] == "event_time_local"
    assert "om_cloud_cover_pct" in df.columns
    assert "om_temperature_c" in df.columns
    assert len(df) == 2
    assert df["station_name"].iloc[0] == "Wanshouxigong"
    assert float(df["om_cloud_cover_pct"].iloc[1]) == 20.0


def test_poc_artifact_exists_optional():
    """If Phase 5a POC was run, meta should declare Asia/Shanghai + m/s."""
    meta = Path("artifacts/openmeteo/poc/wanshouxigong_2015-01-01_2015-01-31.meta.json")
    if not meta.exists():
        return
    payload = json.loads(meta.read_text(encoding="utf-8"))
    assert payload["timezone"] == "Asia/Shanghai"
    assert payload["units"]["wind_speed_unit"] == "ms"
