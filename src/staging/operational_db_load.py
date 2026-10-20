"""Load operational_db CDC batches from MinIO Raw into staging.air_quality_hourly.

Phase 3b of docs/OPERATIONAL_DB_INGESTION_DESIGN.md.

Idempotency:
  - Per-batch ledger in staging.load_registry
    dataset='operational_db_cdc', station_name=<batch file stem>
  - Skip only when registry matches AND staging still has those rows
  - Row grain upsert on (station_name, event_time_local)
  - Upsert will not overwrite File-era rows (event_time < 2016-01-01)
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from typing import Literal, Sequence

import pandas as pd
from minio import Minio

from src.ingestion.db_client import DEFAULT_WATERMARK, SOURCE_IDENTIFIER
from src.processing.operational_db_transform import SCHEMA_VERSION, transform_cdc_records
from src.staging.load import (
    apply_ddl,
    connect,
    fetch_registry,
    upsert_registry,
)
from src.staging.schema import AIR_COLUMNS, TABLE_AIR, copy_sql, frame_to_copy_buffer
from src.utils.minio_client import get_bucket, get_minio_client, get_object_bytes, list_object_names

logger = logging.getLogger(__name__)

DATASET_OPERATIONAL_CDC = "operational_db_cdc"
RAW_PREFIX = "raw/operational_db/"
# Operational channel starts at 2016; never clobber File/UCI archive hours.
FILE_ERA_END = "2015-12-31 23:00:00"

LoadStatus = Literal["loaded", "skipped_identical", "empty"]


@dataclass(frozen=True)
class OperationalStagingLoadResult:
    status: LoadStatus
    source_object_key: str
    source_sha256: str
    schema_version: str
    row_count: int
    quarantine_rows: int
    watermark_start: str | None
    watermark_end: str | None
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


def batch_registry_station(object_key: str) -> str:
    """Registry station_name slot: batch filename stem (unique per CDC object)."""
    name = object_key.replace("\\", "/").rsplit("/", 1)[-1]
    if name.endswith(".json"):
        name = name[: -len(".json")]
    return name


def meta_key_for_batch(object_key: str) -> str:
    return f"{object_key}.meta.json"


def list_cdc_batch_keys(
    *,
    client: Minio | None = None,
    bucket: str | None = None,
    prefix: str = RAW_PREFIX,
) -> list[str]:
    minio = client or get_minio_client()
    bkt = get_bucket(bucket)
    names = list_object_names(minio, bkt, prefix=prefix)
    keys = [
        n
        for n in names
        if n.endswith(".json") and not n.endswith(".meta.json")
    ]
    return sorted(keys)


def staging_operational_watermark(conn=None) -> str:
    """MAX(event_time_local) for operational_db rows, else design default."""
    own = conn is None
    connection = conn or connect()
    try:
        with connection.cursor() as cur:
            cur.execute(
                f"""
                SELECT MAX(event_time_local)
                FROM {TABLE_AIR}
                WHERE source_system = %s
                """,
                (SOURCE_IDENTIFIER,),
            )
            row = cur.fetchone()
        connection.rollback()
        if row is None or row[0] is None:
            return DEFAULT_WATERMARK
        value = row[0]
        if hasattr(value, "strftime"):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return str(value)
    finally:
        if own:
            connection.close()


def _copy_frame(cur, table: str, columns: tuple[str, ...], df: pd.DataFrame) -> None:
    buffer = frame_to_copy_buffer(df, columns)
    cur.copy_expert(copy_sql(table, columns), buffer)


def _count_rows_for_object(conn, object_key: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT COUNT(*) FROM {TABLE_AIR} WHERE source_object_key = %s",
            (object_key,),
        )
        row = cur.fetchone()
    conn.rollback()
    return int(row[0]) if row else 0


def _mark_registry(
    conn,
    *,
    registry_station: str,
    source_object_key: str,
    source_sha256: str,
    row_count: int,
) -> None:
    try:
        with conn.cursor() as cur:
            upsert_registry(
                cur,
                dataset=DATASET_OPERATIONAL_CDC,
                station=registry_station,
                source_object_key=source_object_key,
                source_sha256=source_sha256,
                schema_version=SCHEMA_VERSION,
                row_count=row_count,
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _upsert_sql(columns: tuple[str, ...]) -> str:
    col_list = ", ".join(columns)
    updates = ", ".join(
        f"{c} = EXCLUDED.{c}" for c in columns if c not in {"station_name", "event_time_local"}
    )
    # Do not overwrite File-era archive rows (event_time <= 2015-12-31 23:00).
    return f"""
        INSERT INTO {TABLE_AIR} ({col_list})
        SELECT {col_list} FROM _operational_cdc_batch
        ON CONFLICT (station_name, event_time_local) DO UPDATE SET
            {updates}
        WHERE {TABLE_AIR}.event_time_local > TIMESTAMP '{FILE_ERA_END}'
           OR {TABLE_AIR}.source_system = '{SOURCE_IDENTIFIER}'
    """


def commit_hourly_upsert(
    conn,
    *,
    df: pd.DataFrame,
    source_object_key: str,
    source_sha256: str,
    schema_version: str,
    row_count: int,
    registry_station: str,
) -> None:
    if len(df) != int(row_count):
        raise RuntimeError(f"frame rows {len(df)} != row_count {row_count}")
    if df.duplicated(subset=["station_name", "event_time_local"]).any():
        raise RuntimeError("Duplicate natural key in operational_db batch frame")
    missing = [c for c in AIR_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"frame missing columns: {missing}")

    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE TEMP TABLE _operational_cdc_batch "
                f"(LIKE {TABLE_AIR} INCLUDING DEFAULTS) ON COMMIT DROP"
            )
            _copy_frame(cur, "_operational_cdc_batch", AIR_COLUMNS, df)
            cur.execute(_upsert_sql(AIR_COLUMNS))
            upsert_registry(
                cur,
                dataset=DATASET_OPERATIONAL_CDC,
                station=registry_station,
                source_object_key=source_object_key,
                source_sha256=source_sha256,
                schema_version=schema_version,
                row_count=row_count,
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def load_cdc_batch_object(
    object_key: str,
    conn=None,
    *,
    client: Minio | None = None,
    bucket: str | None = None,
    apply_schema: bool = True,
) -> OperationalStagingLoadResult:
    """Load one MinIO CDC JSON batch into staging (upsert)."""
    own = conn is None
    connection = conn or connect()
    minio = client or get_minio_client()
    bkt = get_bucket(bucket)
    registry_station = batch_registry_station(object_key)

    try:
        if apply_schema:
            apply_ddl(connection)

        meta_key = meta_key_for_batch(object_key)
        sidecar = json.loads(get_object_bytes(minio, bkt, meta_key))
        source_sha256 = str(sidecar.get("source_sha256") or "")
        if not source_sha256:
            raise ValueError(f"sidecar missing source_sha256: {meta_key}")

        # Idempotency: registry match AND rows still present for this object key.
        with connection.cursor() as cur:
            existing = fetch_registry(cur, DATASET_OPERATIONAL_CDC, registry_station)
        connection.rollback()
        if (
            existing is not None
            and existing.source_sha256 == source_sha256
            and existing.schema_version == SCHEMA_VERSION
            and existing.source_object_key == object_key
        ):
            present = _count_rows_for_object(connection, object_key)
            expected = int(existing.row_count)
            if expected == 0 or present == expected:
                return OperationalStagingLoadResult(
                    status="skipped_identical",
                    source_object_key=object_key,
                    source_sha256=source_sha256,
                    schema_version=SCHEMA_VERSION,
                    row_count=existing.row_count,
                    quarantine_rows=0,
                    watermark_start=sidecar.get("watermark_start"),
                    watermark_end=sidecar.get("watermark_end"),
                    message=(
                        "CDC batch already loaded for same object key + sha256 "
                        f"(staging rows={present})"
                    ),
                )
            logger.warning(
                "Registry claims batch loaded but staging rows missing/partial "
                "object=%s expected=%s present=%s - reloading",
                object_key,
                expected,
                present,
            )

        body = get_object_bytes(minio, bkt, object_key)
        body_sha = hashlib.sha256(body).hexdigest()
        if body_sha != source_sha256:
            raise ValueError(
                f"CDC body sha256 mismatch for {object_key}: "
                f"body={body_sha} sidecar={source_sha256}"
            )

        payload = json.loads(body)
        records = payload.get("records") or []
        wm_start = payload.get("watermark_start") or sidecar.get("watermark_start")
        wm_end = payload.get("watermark_end") or sidecar.get("watermark_end")

        if not records:
            _mark_registry(
                connection,
                registry_station=registry_station,
                source_object_key=object_key,
                source_sha256=source_sha256,
                row_count=0,
            )
            return OperationalStagingLoadResult(
                status="empty",
                source_object_key=object_key,
                source_sha256=source_sha256,
                schema_version=SCHEMA_VERSION,
                row_count=0,
                quarantine_rows=0,
                watermark_start=wm_start,
                watermark_end=wm_end,
                message="CDC batch has no records",
            )

        clean, stats = transform_cdc_records(
            records,
            source_object_key=object_key,
            source_sha256=source_sha256,
        )
        if stats["quarantine_rows"] > 0:
            logger.warning(
                "operational_db CDC quarantine dropped rows object=%s "
                "quarantine=%s clean=%s input=%s "
                "(those station/hour keys will not be in staging; watermark may still advance)",
                object_key,
                stats["quarantine_rows"],
                stats["clean_rows"],
                stats["input_rows"],
            )

        if clean.empty:
            _mark_registry(
                connection,
                registry_station=registry_station,
                source_object_key=object_key,
                source_sha256=source_sha256,
                row_count=0,
            )
            return OperationalStagingLoadResult(
                status="empty",
                source_object_key=object_key,
                source_sha256=source_sha256,
                schema_version=SCHEMA_VERSION,
                row_count=0,
                quarantine_rows=stats["quarantine_rows"],
                watermark_start=wm_start,
                watermark_end=wm_end,
                message="all rows quarantined; nothing upserted",
            )

        commit_hourly_upsert(
            connection,
            df=clean,
            source_object_key=object_key,
            source_sha256=source_sha256,
            schema_version=SCHEMA_VERSION,
            row_count=len(clean),
            registry_station=registry_station,
        )
        return OperationalStagingLoadResult(
            status="loaded",
            source_object_key=object_key,
            source_sha256=source_sha256,
            schema_version=SCHEMA_VERSION,
            row_count=len(clean),
            quarantine_rows=stats["quarantine_rows"],
            watermark_start=wm_start,
            watermark_end=wm_end,
            message="upserted operational_db CDC batch into staging.air_quality_hourly",
        )
    finally:
        if own:
            connection.close()


def load_cdc_batches(
    object_keys: Sequence[str] | None = None,
    conn=None,
    *,
    client: Minio | None = None,
    bucket: str | None = None,
    apply_schema: bool = True,
) -> list[OperationalStagingLoadResult]:
    """Load given keys, or every batch under raw/operational_db/."""
    own = conn is None
    connection = conn or connect()
    minio = client or get_minio_client()
    bkt = get_bucket(bucket)
    try:
        if apply_schema:
            apply_ddl(connection)
        keys = list(object_keys) if object_keys is not None else list_cdc_batch_keys(
            client=minio, bucket=bkt
        )
        results: list[OperationalStagingLoadResult] = []
        for key in keys:
            results.append(
                load_cdc_batch_object(
                    key,
                    connection,
                    client=minio,
                    bucket=bkt,
                    apply_schema=False,
                )
            )
        return results
    finally:
        if own:
            connection.close()
