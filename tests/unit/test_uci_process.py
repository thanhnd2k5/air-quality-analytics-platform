"""Unit tests for Phase 4 UCI transform / DQ / processed key builders."""

from __future__ import annotations

import io
from datetime import datetime, timezone

import pandas as pd
import pytest

from src.processing.dq import apply_data_quality
from src.processing.schema import CANONICAL_OUTPUT_COLUMNS, REQUIRED_UCI_COLUMNS
from src.processing.transform import dataframe_to_parquet_bytes, transform_uci_csv_bytes
from src.processing.uci_to_processed import (
    build_meta_key,
    build_processed_key,
    build_quarantine_key,
    station_slug,
)


def _uci_csv_bytes(
    station: str = "Wanshouxigong",
    *,
    rows: list[dict] | None = None,
) -> bytes:
    base_rows = rows or [
        {
            "No": 1,
            "year": 2013,
            "month": 3,
            "day": 1,
            "hour": 0,
            "PM2.5": 10.0,
            "PM10": 20.0,
            "SO2": 1.0,
            "NO2": 2.0,
            "CO": 300.0,
            "O3": 5.0,
            "TEMP": 5.0,
            "PRES": 1010.0,
            "DEWP": -2.0,
            "RAIN": 0.0,
            "wd": "N",
            "WSPM": 1.2,
            "station": station,
        }
    ]
    df = pd.DataFrame(base_rows)
    # Ensure column order matches required set
    df = df[list(REQUIRED_UCI_COLUMNS)]
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


def test_build_processed_and_quarantine_keys():
    key = build_processed_key("Wanshouxigong", process_date="2026-10-07")
    assert (
        key
        == "processed/uci/air_quality/station=Wanshouxigong/process_date=2026-10-07/"
        "wanshouxigong_hourly.parquet"
    )
    assert build_meta_key(key) == (
        "processed/uci/air_quality/station=Wanshouxigong/process_date=2026-10-07/"
        "wanshouxigong_hourly.meta.json"
    )
    qkey = build_quarantine_key("Wanshouxigong", process_date="2026-10-07")
    assert qkey.endswith("wanshouxigong_quarantine.parquet")
    assert "processed/quarantine/uci/air_quality/" in qkey
    assert station_slug("Wanshouxigong") == "wanshouxigong"


def test_transform_builds_event_time_and_canonical_names():
    raw = _uci_csv_bytes()
    df = transform_uci_csv_bytes(
        raw,
        "Wanshouxigong",
        source_file_name="PRSA_Data_Wanshouxigong.csv",
        source_object_key="raw/uci/air_quality/station=Wanshouxigong/x.csv",
        source_sha256="abc",
        process_time="2026-10-07T00:00:00Z",
    )
    assert "event_time_local" in df.columns
    assert df.loc[0, "event_time_local"] == pd.Timestamp("2013-03-01 00:00:00")
    assert "pm25_ug_m3" in df.columns
    assert "PM2.5" not in df.columns
    assert df.loc[0, "station_name"] == "Wanshouxigong"
    assert df.loc[0, "temperature_c"] == 5.0
    assert df.loc[0, "dew_point_c"] == -2.0


def test_transform_rejects_station_mismatch():
    raw = _uci_csv_bytes("Aotizhongxin")
    with pytest.raises(ValueError, match="station_name mismatch"):
        transform_uci_csv_bytes(
            raw,
            "Wanshouxigong",
            source_file_name="x.csv",
            process_time="2026-10-07T00:00:00Z",
        )


def test_dq_flags_missing_and_suspect_cap():
    # Explicit NA in TEMP column (keep column alignment)
    header = ",".join(REQUIRED_UCI_COLUMNS)
    row = (
        "1,2013,3,1,0,999.0,20.0,1.0,2.0,300.0,5.0,NA,1010.0,-2.0,0.0,N,1.2,Wanshouxigong"
    )
    raw = f"{header}\n{row}\n".encode("utf-8")
    canonical = transform_uci_csv_bytes(
        raw,
        "Wanshouxigong",
        source_file_name="x.csv",
        process_time="2026-10-07T00:00:00Z",
    )
    assert pd.isna(canonical.loc[0, "temperature_c"])

    result = apply_data_quality(canonical)
    assert result.quarantine_row_count == 0
    assert len(result.clean) == 1
    row_out = result.clean.iloc[0]
    assert bool(row_out["suspect_cap"]) is True
    assert bool(row_out["has_missing_weather"]) is True
    assert row_out["data_quality_status"] == "SUSPECT_CAP"
    for col in CANONICAL_OUTPUT_COLUMNS:
        assert col in result.clean.columns


def test_dq_quarantines_invalid_negatives():
    raw = _uci_csv_bytes(
        rows=[
            {
                "No": 1,
                "year": 2013,
                "month": 3,
                "day": 1,
                "hour": 0,
                "PM2.5": -5.0,
                "PM10": 20.0,
                "SO2": 1.0,
                "NO2": 2.0,
                "CO": 300.0,
                "O3": 5.0,
                "TEMP": 5.0,
                "PRES": 1010.0,
                "DEWP": -2.0,
                "RAIN": 0.0,
                "wd": "N",
                "WSPM": 1.2,
                "station": "Wanshouxigong",
            },
            {
                "No": 2,
                "year": 2013,
                "month": 3,
                "day": 1,
                "hour": 1,
                "PM2.5": 10.0,
                "PM10": 20.0,
                "SO2": 1.0,
                "NO2": 2.0,
                "CO": 300.0,
                "O3": 5.0,
                "TEMP": 5.0,
                "PRES": 1010.0,
                "DEWP": -2.0,
                "RAIN": 0.0,
                "wd": "N",
                "WSPM": 1.2,
                "station": "Wanshouxigong",
            },
        ]
    )
    canonical = transform_uci_csv_bytes(
        raw,
        "Wanshouxigong",
        source_file_name="x.csv",
        process_time="2026-10-07T00:00:00Z",
    )
    result = apply_data_quality(canonical)
    assert result.quarantine_row_count == 1
    assert len(result.clean) == 1
    assert result.quarantine.iloc[0]["data_quality_status"] == "QUARANTINED_NEGATIVE"
    assert result.clean.iloc[0]["pm25_ug_m3"] == 10.0


def test_dq_fails_on_duplicate_natural_key():
    raw = _uci_csv_bytes(
        rows=[
            {
                "No": 1,
                "year": 2013,
                "month": 3,
                "day": 1,
                "hour": 0,
                "PM2.5": 10.0,
                "PM10": 20.0,
                "SO2": 1.0,
                "NO2": 2.0,
                "CO": 300.0,
                "O3": 5.0,
                "TEMP": 5.0,
                "PRES": 1010.0,
                "DEWP": -2.0,
                "RAIN": 0.0,
                "wd": "N",
                "WSPM": 1.2,
                "station": "Wanshouxigong",
            },
            {
                "No": 2,
                "year": 2013,
                "month": 3,
                "day": 1,
                "hour": 0,
                "PM2.5": 11.0,
                "PM10": 21.0,
                "SO2": 1.0,
                "NO2": 2.0,
                "CO": 300.0,
                "O3": 5.0,
                "TEMP": 5.0,
                "PRES": 1010.0,
                "DEWP": -2.0,
                "RAIN": 0.0,
                "wd": "N",
                "WSPM": 1.2,
                "station": "Wanshouxigong",
            },
        ]
    )
    canonical = transform_uci_csv_bytes(
        raw,
        "Wanshouxigong",
        source_file_name="x.csv",
        process_time="2026-10-07T00:00:00Z",
    )
    with pytest.raises(ValueError, match="Duplicate natural key"):
        apply_data_quality(canonical)


def test_parquet_roundtrip_preserves_rows():
    raw = _uci_csv_bytes()
    canonical = transform_uci_csv_bytes(
        raw,
        "Wanshouxigong",
        source_file_name="x.csv",
        process_time=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    result = apply_data_quality(canonical)
    blob = dataframe_to_parquet_bytes(result.clean)
    restored = pd.read_parquet(io.BytesIO(blob))
    assert len(restored) == 1
    assert "pm25_ug_m3" in restored.columns
    assert restored.iloc[0]["data_quality_status"] == "OK"
