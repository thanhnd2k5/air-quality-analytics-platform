"""Source-to-target checks for PostgreSQL staging (Phase 6)."""

from __future__ import annotations

from src.staging.schema import (
    AIR_COLUMN_TYPES,
    DATASET_AIR,
    DATASET_OM,
    EXPECTED_END,
    EXPECTED_ROW_COUNT,
    EXPECTED_START,
    EXPECTED_STATION_COUNT,
    OM_COLUMN_TYPES,
    REFERENCE_COLUMN_TYPES,
    TABLE_AIR,
    TABLE_OM,
    TABLE_REFERENCE,
)
from src.staging.load import resolve_latest_sidecar
from src.staging.schema import require_sidecar_fields
from src.utils.minio_client import get_bucket, get_minio_client


def _column_types(cur, table: str) -> dict[str, str]:
    schema, name = table.split(".", 1)
    cur.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        ORDER BY ordinal_position
        """,
        (schema, name),
    )
    return {row[0]: row[1] for row in cur.fetchall()}


def _hourly_stats(cur, table: str, stations: list[str]) -> list[dict]:
    cur.execute(
        f"""
        SELECT station_name,
               COUNT(*) AS row_count,
               COUNT(*) - COUNT(DISTINCT (station_name, event_time_local)) AS duplicate_keys,
               SUM(CASE WHEN station_name IS NULL OR event_time_local IS NULL THEN 1 ELSE 0 END) AS null_keys,
               MIN(event_time_local)::text,
               MAX(event_time_local)::text
        FROM {table}
        WHERE station_name = ANY(%s)
        GROUP BY station_name
        ORDER BY station_name
        """,
        (stations,),
    )
    rows = []
    for station, row_count, duplicate_keys, null_keys, min_time, max_time in cur.fetchall():
        rows.append(
            {
                "station_name": station,
                "row_count": int(row_count),
                "duplicate_keys": int(duplicate_keys),
                "null_keys": int(null_keys),
                "min_event_time": min_time,
                "max_event_time": max_time,
            }
        )
    return rows


def _source_row_count(station: str, dataset: str, client, bucket: str) -> tuple[str, int]:
    from src.staging.schema import OM_PROCESSED_PREFIX, UCI_PROCESSED_PREFIX

    prefix = UCI_PROCESSED_PREFIX if dataset == DATASET_AIR else OM_PROCESSED_PREFIX
    key, sidecar = resolve_latest_sidecar(station, prefix, client=client, bucket=bucket)
    _sha, _schema, row_count = require_sidecar_fields(sidecar)
    return key, row_count


def reconcile(
    conn,
    stations: list[str],
    *,
    expect_full: bool = False,
    client=None,
    bucket: str | None = None,
) -> dict:
    """Compare staging rows to processed sidecars. Raises nothing; returns errors."""
    minio = client or get_minio_client()
    bkt = get_bucket(bucket)
    errors: list[str] = []

    with conn.cursor() as cur:
        air_types = _column_types(cur, TABLE_AIR)
        om_types = _column_types(cur, TABLE_OM)
        ref_types = _column_types(cur, TABLE_REFERENCE)
        air_stats = _hourly_stats(cur, TABLE_AIR, stations)
        om_stats = _hourly_stats(cur, TABLE_OM, stations)
        cur.execute(f"SELECT COUNT(*) FROM {TABLE_REFERENCE}")
        reference_count = int(cur.fetchone()[0])
        cur.execute(
            f"""
            SELECT COUNT(*) FROM {TABLE_REFERENCE}
            WHERE station_id IS NULL OR station_name IS NULL
               OR latitude IS NULL OR longitude IS NULL
            """
        )
        reference_null_keys = int(cur.fetchone()[0])
        cur.execute(
            f"""
            SELECT COUNT(*) - COUNT(DISTINCT station_name)
            FROM {TABLE_REFERENCE}
            """
        )
        reference_duplicate_names = int(cur.fetchone()[0])
        cur.execute(f"SELECT COUNT(DISTINCT station_name) FROM {TABLE_AIR}")
        air_station_count = int(cur.fetchone()[0])
        cur.execute(f"SELECT COUNT(DISTINCT station_name) FROM {TABLE_OM}")
        om_station_count = int(cur.fetchone()[0])

    def _check_types(label: str, actual: dict[str, str], expected: dict[str, str]) -> None:
        for column, data_type in expected.items():
            if actual.get(column) != data_type:
                errors.append(
                    f"{label}.{column} type {actual.get(column)!r} != {data_type!r}"
                )

    _check_types(TABLE_AIR, air_types, AIR_COLUMN_TYPES)
    _check_types(TABLE_OM, om_types, OM_COLUMN_TYPES)
    _check_types(TABLE_REFERENCE, ref_types, REFERENCE_COLUMN_TYPES)

    def _check_hourly(dataset: str, stats: list[dict]) -> dict:
        by_station = {row["station_name"]: row for row in stats}
        source_total = 0
        target_total = 0
        per_station = []
        for station in stations:
            source_key, source_count = _source_row_count(station, dataset, minio, bkt)
            target = by_station.get(station)
            target_count = int(target["row_count"]) if target else 0
            source_total += source_count
            target_total += target_count
            entry = {
                "station": station,
                "source_object_key": source_key,
                "source_row_count": source_count,
                "target_row_count": target_count,
                "duplicate_keys": int(target["duplicate_keys"]) if target else None,
                "null_keys": int(target["null_keys"]) if target else None,
                "min_event_time": target["min_event_time"] if target else None,
                "max_event_time": target["max_event_time"] if target else None,
            }
            per_station.append(entry)
            if target is None:
                errors.append(f"{dataset} missing station {station}")
                continue
            if target_count != source_count:
                errors.append(
                    f"{dataset} {station} target {target_count} != source {source_count}"
                )
            if target["duplicate_keys"] != 0:
                errors.append(f"{dataset} {station} duplicate keys {target['duplicate_keys']}")
            if target["null_keys"] != 0:
                errors.append(f"{dataset} {station} null natural keys {target['null_keys']}")
            min_time = (target["min_event_time"] or "")[:19]
            max_time = (target["max_event_time"] or "")[:19]
            entry["min_event_time"] = min_time or None
            entry["max_event_time"] = max_time or None
            if source_count == EXPECTED_ROW_COUNT:
                if min_time != EXPECTED_START or max_time != EXPECTED_END:
                    errors.append(
                        f"{dataset} {station} date range "
                        f"{min_time} → {max_time} "
                        f"!= {EXPECTED_START} → {EXPECTED_END}"
                    )
        return {
            "source_row_count": source_total,
            "target_row_count": target_total,
            "station_count": len(by_station),
            "stations": per_station,
        }

    air_report = _check_hourly(DATASET_AIR, air_stats)
    om_report = _check_hourly(DATASET_OM, om_stats)

    if reference_count != EXPECTED_STATION_COUNT:
        errors.append(
            f"station_reference count {reference_count} != {EXPECTED_STATION_COUNT}"
        )
    if reference_null_keys != 0:
        errors.append(f"station_reference null required fields {reference_null_keys}")
    if reference_duplicate_names != 0:
        errors.append(f"station_reference duplicate station_name {reference_duplicate_names}")

    if expect_full:
        if len(stations) != EXPECTED_STATION_COUNT:
            errors.append(
                f"expect_full but station list has {len(stations)} != {EXPECTED_STATION_COUNT}"
            )
        if air_station_count != EXPECTED_STATION_COUNT:
            errors.append(
                f"air_quality_hourly station_count {air_station_count} != {EXPECTED_STATION_COUNT}"
            )
        if om_station_count != EXPECTED_STATION_COUNT:
            errors.append(
                f"weather_openmeteo_hourly station_count {om_station_count} != {EXPECTED_STATION_COUNT}"
            )

    return {
        "expect_full": expect_full,
        "ok": not errors,
        "errors": errors,
        "air_quality_hourly": air_report,
        "weather_openmeteo_hourly": om_report,
        "station_reference": {
            "target_row_count": reference_count,
            "duplicate_station_name": reference_duplicate_names,
            "null_required": reference_null_keys,
        },
    }
