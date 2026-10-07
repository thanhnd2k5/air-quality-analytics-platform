"""Load processed Parquet and station reference into PostgreSQL staging."""

from __future__ import annotations

import hashlib
import io
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import pandas as pd
import psycopg2
from minio import Minio

from src.staging.schema import (
    AIR_COLUMNS,
    DATASET_AIR,
    DATASET_OM,
    DATASET_REFERENCE,
    OM_COLUMNS_OUT,
    OM_PROCESSED_PREFIX,
    REFERENCE_REGISTRY_STATION,
    STATION_REFERENCE_COLUMNS,
    STATION_REFERENCE_SCHEMA_VERSION,
    TABLE_AIR,
    TABLE_OM,
    TABLE_REFERENCE,
    UCI_PROCESSED_PREFIX,
    RegistryRow,
    assert_frame_ready,
    assert_loadable_object_key,
    copy_sql,
    ddl_path,
    frame_to_copy_buffer,
    meta_key_for,
    should_skip_load,
    require_sidecar_fields,
    select_latest_processed_key,
)
from src.utils.minio_client import (
    get_bucket,
    get_minio_client,
    get_object_bytes,
    list_object_names,
)

LoadStatus = Literal["loaded", "skipped_identical"]


@dataclass(frozen=True)
class LoadResult:
    dataset: str
    station: str
    status: LoadStatus
    source_object_key: str
    source_sha256: str
    schema_version: str
    row_count: int
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


def connect():
    password = os.getenv("POSTGRES_PASSWORD")
    if not password:
        raise ValueError("Missing required environment variable: POSTGRES_PASSWORD")
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "air_quality_dw"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=password,
    )


def apply_ddl(conn) -> None:
    sql_path = ddl_path()
    script = sql_path.read_text(encoding="utf-8")
    statements = [chunk.strip() for chunk in script.split(";") if chunk.strip()]
    previous = conn.autocommit
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            for statement in statements:
                cur.execute(statement)
    finally:
        conn.autocommit = previous


def fetch_registry(cur, dataset: str, station: str) -> RegistryRow | None:
    cur.execute(
        """
        SELECT source_object_key, source_sha256, schema_version, row_count
        FROM staging.load_registry
        WHERE dataset = %s AND station_name = %s
        """,
        (dataset, station),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return RegistryRow(
        source_object_key=row[0],
        source_sha256=row[1],
        schema_version=row[2],
        row_count=int(row[3]),
    )


def upsert_registry(
    cur,
    *,
    dataset: str,
    station: str,
    source_object_key: str,
    source_sha256: str,
    schema_version: str,
    row_count: int,
) -> None:
    cur.execute(
        """
        INSERT INTO staging.load_registry (
            dataset, station_name, source_object_key, source_sha256,
            schema_version, row_count, loaded_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (dataset, station_name) DO UPDATE SET
            source_object_key = EXCLUDED.source_object_key,
            source_sha256 = EXCLUDED.source_sha256,
            schema_version = EXCLUDED.schema_version,
            row_count = EXCLUDED.row_count,
            loaded_at = NOW()
        """,
        (dataset, station, source_object_key, source_sha256, schema_version, row_count),
    )


def _copy_frame(cur, table: str, columns: tuple[str, ...], df: pd.DataFrame) -> None:
    buffer = frame_to_copy_buffer(df, columns)
    cur.copy_expert(copy_sql(table, columns), buffer)


def commit_hourly_replace(
    conn,
    *,
    dataset: str,
    table: str,
    columns: tuple[str, ...],
    station: str,
    df: pd.DataFrame,
    source_object_key: str,
    source_sha256: str,
    schema_version: str,
    row_count: int,
) -> None:
    assert_frame_ready(df, station=station, columns=columns, row_count=row_count)
    try:
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM {table} WHERE station_name = %s", (station,))
            _copy_frame(cur, table, columns, df)
            upsert_registry(
                cur,
                dataset=dataset,
                station=station,
                source_object_key=source_object_key,
                source_sha256=source_sha256,
                schema_version=schema_version,
                row_count=row_count,
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def commit_reference_replace(
    conn,
    df: pd.DataFrame,
    *,
    source_object_key: str,
    source_sha256: str,
    schema_version: str,
) -> None:
    missing = [col for col in STATION_REFERENCE_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"stations.csv missing columns: {missing}")
    if df["station_name"].duplicated().any() or df["station_id"].duplicated().any():
        raise RuntimeError("Duplicate station_id or station_name in stations.csv")
    row_count = len(df)
    try:
        with conn.cursor() as cur:
            cur.execute(f"TRUNCATE {TABLE_REFERENCE}")
            _copy_frame(cur, TABLE_REFERENCE, STATION_REFERENCE_COLUMNS, df)
            upsert_registry(
                cur,
                dataset=DATASET_REFERENCE,
                station=REFERENCE_REGISTRY_STATION,
                source_object_key=source_object_key,
                source_sha256=source_sha256,
                schema_version=schema_version,
                row_count=row_count,
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def count_loaded_rows(conn, table: str, station: str | None) -> int:
    with conn.cursor() as cur:
        if station is None:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
        else:
            cur.execute(f"SELECT COUNT(*) FROM {table} WHERE station_name = %s", (station,))
        row = cur.fetchone()
    conn.rollback()
    return int(row[0]) if row else 0


def _registry_decision(
    conn,
    dataset: str,
    station: str,
    source_sha256: str,
    schema_version: str,
    row_count: int,
    source_object_key: str,
    loaded_row_count: int,
) -> RegistryRow | None:
    with conn.cursor() as cur:
        existing = fetch_registry(cur, dataset, station)
    conn.rollback()
    if should_skip_load(
        existing,
        source_sha256=source_sha256,
        schema_version=schema_version,
        row_count=row_count,
        source_object_key=source_object_key,
        loaded_row_count=loaded_row_count,
    ):
        return existing
    return None


def resolve_latest_sidecar(
    station: str,
    prefix_template: str,
    *,
    client: Minio | None = None,
    bucket: str | None = None,
) -> tuple[str, dict]:
    minio = client or get_minio_client()
    bkt = get_bucket(bucket)
    prefix = prefix_template.format(station=station)
    names = list_object_names(minio, bkt, prefix=prefix)
    if not names:
        raise FileNotFoundError(f"No processed objects under prefix {prefix}")
    parquet_key = select_latest_processed_key(names)
    assert_loadable_object_key(parquet_key)
    meta_key = meta_key_for(parquet_key)
    sidecar = json.loads(get_object_bytes(minio, bkt, meta_key))
    return parquet_key, sidecar


def _read_parquet(client: Minio, bucket: str, object_key: str) -> pd.DataFrame:
    assert_loadable_object_key(object_key)
    payload = get_object_bytes(client, bucket, object_key)
    return pd.read_parquet(io.BytesIO(payload))


def _load_hourly(
    conn,
    *,
    dataset: str,
    table: str,
    columns: tuple[str, ...],
    prefix_template: str,
    station: str,
    client: Minio | None = None,
    bucket: str | None = None,
) -> LoadResult:
    minio = client or get_minio_client()
    bkt = get_bucket(bucket)
    parquet_key, sidecar = resolve_latest_sidecar(
        station, prefix_template, client=minio, bucket=bkt
    )
    source_sha256, schema_version, row_count = require_sidecar_fields(sidecar)
    loaded_row_count = count_loaded_rows(conn, table, station)
    if _registry_decision(
        conn,
        dataset,
        station,
        source_sha256,
        schema_version,
        row_count,
        parquet_key,
        loaded_row_count,
    ):
        return LoadResult(
            dataset=dataset,
            station=station,
            status="skipped_identical",
            source_object_key=parquet_key,
            source_sha256=source_sha256,
            schema_version=schema_version,
            row_count=row_count,
            message="staging already loaded for same object key, source hash, schema, and row count",
        )
    frame = _read_parquet(minio, bkt, parquet_key)
    commit_hourly_replace(
        conn,
        dataset=dataset,
        table=table,
        columns=columns,
        station=station,
        df=frame,
        source_object_key=parquet_key,
        source_sha256=source_sha256,
        schema_version=schema_version,
        row_count=row_count,
    )
    return LoadResult(
        dataset=dataset,
        station=station,
        status="loaded",
        source_object_key=parquet_key,
        source_sha256=source_sha256,
        schema_version=schema_version,
        row_count=row_count,
        message="replaced station slice in staging",
    )


def reference_object_key(path: Path) -> str:
    """Stable registry identity. Host and Airflow see different absolute paths."""
    name = path.name
    parent = path.parent.name
    if parent:
        return f"data/raw/reference/{name}" if parent == "reference" else f"{parent}/{name}"
    return name


def stations_csv_path(path: Path | None = None) -> Path:
    if path is not None:
        return path
    env = os.getenv("STATIONS_CSV")
    if env:
        return Path(env)
    return Path("data/raw/reference/stations.csv")


def load_station_reference(
    conn=None,
    *,
    csv_path: Path | None = None,
    apply_schema: bool = True,
) -> LoadResult:
    own = conn is None
    connection = conn or connect()
    path = stations_csv_path(csv_path)
    try:
        if apply_schema:
            apply_ddl(connection)
        payload = path.read_bytes()
        source_sha256 = hashlib.sha256(payload).hexdigest()
        frame = pd.read_csv(io.BytesIO(payload))
        row_count = len(frame)
        source_key = reference_object_key(path)
        loaded_row_count = count_loaded_rows(connection, TABLE_REFERENCE, None)
        if _registry_decision(
            connection,
            DATASET_REFERENCE,
            REFERENCE_REGISTRY_STATION,
            source_sha256,
            STATION_REFERENCE_SCHEMA_VERSION,
            row_count,
            source_key,
            loaded_row_count,
        ):
            return LoadResult(
                dataset=DATASET_REFERENCE,
                station=REFERENCE_REGISTRY_STATION,
                status="skipped_identical",
                source_object_key=source_key,
                source_sha256=source_sha256,
                schema_version=STATION_REFERENCE_SCHEMA_VERSION,
                row_count=row_count,
                message="station_reference already loaded for same file sha256 + schema_version",
            )
        commit_reference_replace(
            connection,
            frame,
            source_object_key=source_key,
            source_sha256=source_sha256,
            schema_version=STATION_REFERENCE_SCHEMA_VERSION,
        )
        return LoadResult(
            dataset=DATASET_REFERENCE,
            station=REFERENCE_REGISTRY_STATION,
            status="loaded",
            source_object_key=source_key,
            source_sha256=source_sha256,
            schema_version=STATION_REFERENCE_SCHEMA_VERSION,
            row_count=row_count,
            message="replaced station_reference",
        )
    finally:
        if own:
            connection.close()


def load_air_quality_station(
    station: str,
    conn=None,
    *,
    client: Minio | None = None,
    bucket: str | None = None,
    apply_schema: bool = True,
) -> LoadResult:
    own = conn is None
    connection = conn or connect()
    try:
        if apply_schema:
            apply_ddl(connection)
        return _load_hourly(
            connection,
            dataset=DATASET_AIR,
            table=TABLE_AIR,
            columns=AIR_COLUMNS,
            prefix_template=UCI_PROCESSED_PREFIX,
            station=station,
            client=client,
            bucket=bucket,
        )
    finally:
        if own:
            connection.close()


def load_openmeteo_station(
    station: str,
    conn=None,
    *,
    client: Minio | None = None,
    bucket: str | None = None,
    apply_schema: bool = True,
) -> LoadResult:
    own = conn is None
    connection = conn or connect()
    try:
        if apply_schema:
            apply_ddl(connection)
        return _load_hourly(
            connection,
            dataset=DATASET_OM,
            table=TABLE_OM,
            columns=OM_COLUMNS_OUT,
            prefix_template=OM_PROCESSED_PREFIX,
            station=station,
            client=client,
            bucket=bucket,
        )
    finally:
        if own:
            connection.close()


def load_stations(
    stations: list[str],
    *,
    include_reference: bool = True,
    datasets: tuple[str, ...] = (DATASET_AIR, DATASET_OM),
    csv_path: Path | None = None,
) -> list[LoadResult]:
    connection = connect()
    results: list[LoadResult] = []
    try:
        apply_ddl(connection)
        if include_reference:
            results.append(
                load_station_reference(connection, csv_path=csv_path, apply_schema=False)
            )
        for station in stations:
            if DATASET_AIR in datasets:
                results.append(
                    load_air_quality_station(station, connection, apply_schema=False)
                )
            if DATASET_OM in datasets:
                results.append(
                    load_openmeteo_station(station, connection, apply_schema=False)
                )
        return results
    finally:
        connection.close()
