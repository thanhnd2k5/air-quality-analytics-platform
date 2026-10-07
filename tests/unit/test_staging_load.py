"""Unit tests for Phase 6 staging load decisions (no live Postgres)."""

from __future__ import annotations

import pandas as pd
import pytest

from src.processing.openmeteo_schema import CANONICAL_OUTPUT_COLUMNS as OM_COLUMNS
from src.processing.schema import CANONICAL_OUTPUT_COLUMNS as UCI_COLUMNS
from src.staging.load import commit_hourly_replace, commit_reference_replace
from src.staging.schema import (
    AIR_COLUMN_TYPES,
    OM_COLUMN_TYPES,
    REFERENCE_COLUMN_TYPES,
    RegistryRow,
    STATION_REFERENCE_COLUMNS,
    TABLE_AIR,
    TABLE_OM,
    TABLE_REFERENCE,
    assert_frame_ready,
    assert_loadable_object_key,
    ddl_path,
    frame_to_copy_buffer,
    registry_matches,
    select_latest_processed_key,
)


class _Cursor:
    def __init__(self, fetchone_result=None):
        self.ops: list[tuple] = []
        self._fetch = fetchone_result

    def execute(self, sql, params=None):
        self.ops.append(("execute", " ".join(sql.split()), params))

    def copy_expert(self, sql, fileobj):
        self.ops.append(("copy", " ".join(sql.split()), fileobj.read()))

    def fetchone(self):
        return self._fetch

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class RecordingConn:
    def __init__(self, fetchone_result=None):
        self.cur = _Cursor(fetchone_result)
        self.committed = 0
        self.rolled_back = 0

    def cursor(self):
        return self.cur

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled_back += 1


def _air_frame(station: str = "Wanshouxigong", *, rows: int = 1) -> pd.DataFrame:
    records = []
    for index in range(rows):
        row = {col: None for col in UCI_COLUMNS}
        row.update(
            {
                "source_row_no": index + 1,
                "event_time_local": pd.Timestamp("2013-03-01 00:00:00") + pd.Timedelta(hours=index),
                "station_name": station,
                "pm25_ug_m3": 10.0 if index == 0 else None,
                "has_missing_pollutant": False,
                "has_missing_weather": True,
                "suspect_cap": False,
                "data_quality_status": "OK",
                "wind_direction": "N",
                "process_time": "2026-10-07T00:00:00Z",
                "source_system": "uci_prsa",
                "source_sha256": "abc",
                "source_object_key": "processed/uci/air_quality/x.parquet",
                "source_file_name": "x.csv",
            }
        )
        records.append(row)
    return pd.DataFrame(records)


def test_registry_matches_only_when_sha_schema_and_count_agree():
    existing = RegistryRow("k", "abc", "1.0.0", 35064)
    assert registry_matches(existing, source_sha256="abc", schema_version="1.0.0", row_count=35064)
    assert not registry_matches(None, source_sha256="abc", schema_version="1.0.0", row_count=1)
    assert not registry_matches(existing, source_sha256="zzz", schema_version="1.0.0", row_count=35064)
    assert not registry_matches(existing, source_sha256="abc", schema_version="2.0.0", row_count=35064)
    assert not registry_matches(existing, source_sha256="abc", schema_version="1.0.0", row_count=1)


def test_select_latest_ignores_quarantine_and_older_partition():
    keys = [
        "processed/quarantine/uci/air_quality/station=X/process_date=2026-10-08/x.parquet",
        "processed/uci/air_quality/station=X/process_date=2026-10-01/x_hourly.parquet",
        "processed/uci/air_quality/station=X/process_date=2026-10-07/x_hourly.parquet",
        "processed/uci/air_quality/station=X/process_date=2026-10-07/x_hourly.meta.json",
    ]
    chosen = select_latest_processed_key(keys)
    assert chosen.endswith("process_date=2026-10-07/x_hourly.parquet")
    assert "quarantine" not in chosen


def test_reject_quarantine_key():
    with pytest.raises(ValueError, match="quarantine"):
        assert_loadable_object_key(
            "processed/quarantine/uci/air_quality/station=X/process_date=2026-10-07/x.parquet"
        )


def test_ddl_declares_canonical_columns_and_keys():
    sql = ddl_path().read_text(encoding="utf-8")
    for column in UCI_COLUMNS:
        assert column in sql
    for column in OM_COLUMNS:
        assert column in sql
    for column in STATION_REFERENCE_COLUMNS:
        assert column in sql
    assert "PRIMARY KEY (station_name, event_time_local)" in sql
    assert "station_name TEXT NOT NULL UNIQUE" in sql
    assert "staging.load_registry" in sql
    assert set(AIR_COLUMN_TYPES) == set(UCI_COLUMNS)
    assert set(OM_COLUMN_TYPES) == set(OM_COLUMNS)
    assert set(REFERENCE_COLUMN_TYPES) == set(STATION_REFERENCE_COLUMNS)


def test_replace_deletes_station_then_copies():
    conn = RecordingConn()
    frame = _air_frame()
    commit_hourly_replace(
        conn,
        dataset="air_quality_hourly",
        table=TABLE_AIR,
        columns=UCI_COLUMNS,
        station="Wanshouxigong",
        df=frame,
        source_object_key="processed/uci/air_quality/station=Wanshouxigong/x.parquet",
        source_sha256="abc",
        schema_version="1.0.0",
        row_count=1,
    )
    kinds = [op[0] for op in conn.cur.ops]
    sqls = [op[1] for op in conn.cur.ops]
    assert "copy" in kinds
    assert any(sql.startswith(f"DELETE FROM {TABLE_AIR}") for sql in sqls)
    assert any("INSERT INTO staging.load_registry" in sql for sql in sqls)
    assert conn.committed == 1
    copy_body = next(op[2] for op in conn.cur.ops if op[0] == "copy")
    assert "Wanshouxigong" in copy_body
    assert "true" in copy_body or "false" in copy_body


def test_duplicate_natural_key_does_not_copy():
    frame = _air_frame(rows=2)
    frame.loc[1, "event_time_local"] = frame.loc[0, "event_time_local"]
    conn = RecordingConn()
    with pytest.raises(RuntimeError, match="Duplicate"):
        commit_hourly_replace(
            conn,
            dataset="air_quality_hourly",
            table=TABLE_AIR,
            columns=UCI_COLUMNS,
            station="Wanshouxigong",
            df=frame,
            source_object_key="k",
            source_sha256="abc",
            schema_version="1.0.0",
            row_count=2,
        )
    assert conn.cur.ops == []
    assert conn.committed == 0


def test_reference_replace_truncates_full_table():
    frame = pd.DataFrame(
        [
            {
                "station_id": 1,
                "station_code": "Aotizhongxin",
                "station_name": "Aotizhongxin",
                "latitude": 39.9,
                "longitude": 116.4,
                "district": "Chaoyang",
                "coordinate_status": "LITERATURE",
                "metadata_source": "paper",
                "source_url": "https://example.test",
                "district_source": "src",
                "district_source_url": "https://example.test/d",
                "notes": "ok",
            }
        ]
    )
    conn = RecordingConn()
    commit_reference_replace(
        conn,
        frame,
        source_object_key="data/raw/reference/stations.csv",
        source_sha256="fff",
        schema_version="1.0.0",
    )
    sqls = [op[1] for op in conn.cur.ops]
    assert any(sql.startswith(f"TRUNCATE {TABLE_REFERENCE}") for sql in sqls)
    assert not any(sql.startswith("DELETE FROM") for sql in sqls)
    assert conn.committed == 1


def test_copy_buffer_null_and_timestamp():
    frame = _air_frame()
    frame.loc[0, "pm25_ug_m3"] = None
    buffer = frame_to_copy_buffer(frame, UCI_COLUMNS)
    text = buffer.read()
    assert "2013-03-01 00:00:00" in text
    assert "2013-03-01T" not in text
    # null measure becomes an empty CSV field, not the string nan
    assert "nan" not in text.lower()


def test_row_count_mismatch_rejected():
    frame = _air_frame()
    with pytest.raises(RuntimeError, match="row count"):
        assert_frame_ready(frame, station="Wanshouxigong", columns=UCI_COLUMNS, row_count=2)


def test_openmeteo_table_constant_differs_from_uci():
    assert TABLE_OM != TABLE_AIR
    assert "om_cloud_cover_pct" in OM_COLUMNS
