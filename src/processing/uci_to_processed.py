"""Process UCI raw MinIO objects into processed Parquet (Phase 4)."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

from minio import Minio

from src.processing.dq import apply_data_quality
from src.processing.schema import SCHEMA_VERSION, SOURCE_SYSTEM
from src.processing.transform import dataframe_to_parquet_bytes, transform_uci_csv_bytes
from src.utils.minio_client import (
    get_bucket,
    get_minio_client,
    get_object_bytes,
    get_object_metadata,
    list_object_names,
    object_exists,
    put_bytes,
)
from src.validation.uci_raw import load_inventory


ProcessStatus = Literal["uploaded", "skipped_identical", "failed"]

_RAW_PREFIX = "raw/uci/air_quality/station={station}/"
_INGESTION_DATE_RE = re.compile(r"ingestion_date=(\d{4}-\d{2}-\d{2})")


@dataclass(frozen=True)
class ProcessResult:
    station: str
    status: ProcessStatus
    raw_object_key: str
    processed_object_key: str
    meta_key: str
    quarantine_object_key: str
    sha256: str
    byte_size: int
    row_count: int
    quarantine_row_count: int
    process_date: str
    process_ts: str
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


def station_slug(station: str) -> str:
    return station.strip().lower()


def build_processed_key(
    station: str,
    process_date: str | date | None = None,
) -> str:
    day = _normalize_day(process_date)
    slug = station_slug(station)
    return (
        f"processed/uci/air_quality/station={station}/"
        f"process_date={day}/{slug}_hourly.parquet"
    )


def build_quarantine_key(
    station: str,
    process_date: str | date | None = None,
) -> str:
    day = _normalize_day(process_date)
    slug = station_slug(station)
    return (
        f"processed/quarantine/uci/air_quality/station={station}/"
        f"process_date={day}/{slug}_quarantine.parquet"
    )


def build_meta_key(processed_object_key: str) -> str:
    if processed_object_key.endswith(".parquet"):
        return processed_object_key[: -len(".parquet")] + ".meta.json"
    return f"{processed_object_key}.meta.json"


def resolve_latest_raw_object_key(
    station: str,
    *,
    client: Minio | None = None,
    bucket: str | None = None,
) -> str:
    """Pick the latest raw CSV for a station (by ingestion_date, then key)."""
    minio = client or get_minio_client()
    bkt = get_bucket(bucket)
    prefix = _RAW_PREFIX.format(station=station)
    names = list_object_names(minio, bkt, prefix=prefix)
    csvs = [n for n in names if n.endswith(".csv") and not n.endswith(".meta.json")]
    if not csvs:
        raise FileNotFoundError(f"No raw CSV objects under prefix {prefix}")

    def sort_key(object_name: str) -> tuple[str, str]:
        match = _INGESTION_DATE_RE.search(object_name)
        day = match.group(1) if match else ""
        return (day, object_name)

    return sorted(csvs, key=sort_key)[-1]


def list_inventory_stations(inventory_path: Path | None = None) -> list[str]:
    return sorted(load_inventory(inventory_path).keys())


def process_station_to_processed(
    station: str,
    *,
    client: Minio | None = None,
    bucket: str | None = None,
    process_date: str | date | None = None,
    raw_object_key: str | None = None,
) -> ProcessResult:
    """
    Resolve raw → transform → DQ → upload Parquet + sidecar (+ quarantine if any).

    Idempotency:
    - processed missing → upload
    - same sha256 → skip
    - different sha256 same key → fail (no overwrite)
    """
    minio = client or get_minio_client()
    bkt = get_bucket(bucket)
    day = _normalize_day(process_date)
    # Deterministic lineage timestamp for a given process_date (reproducible Parquet).
    process_ts = f"{day}T00:00:00Z"
    run_ts = _utc_now_iso()

    raw_key = raw_object_key or resolve_latest_raw_object_key(
        station, client=minio, bucket=bkt
    )
    raw_bytes = get_object_bytes(minio, bkt, raw_key)
    source_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    source_file_name = raw_key.rsplit("/", 1)[-1]

    # Prefer checksum from raw user-metadata when present
    raw_meta = get_object_metadata(minio, bkt, raw_key)
    if raw_meta.get("sha256"):
        source_sha256 = raw_meta["sha256"]

    processed_key = build_processed_key(station, day)
    meta_key = build_meta_key(processed_key)
    quarantine_key = build_quarantine_key(station, day)

    # Idempotency: same source + schema at this key → skip (before rebuild).
    if object_exists(minio, bkt, processed_key):
        existing_sidecar: dict = {}
        if object_exists(minio, bkt, meta_key):
            existing_sidecar = json.loads(get_object_bytes(minio, bkt, meta_key))
        existing_user = get_object_metadata(minio, bkt, processed_key)
        same_source = existing_sidecar.get("source_sha256") == source_sha256
        same_schema = existing_sidecar.get("schema_version") == SCHEMA_VERSION
        if same_source and same_schema:
            return ProcessResult(
                station=station,
                status="skipped_identical",
                raw_object_key=raw_key,
                processed_object_key=processed_key,
                meta_key=meta_key,
                quarantine_object_key=existing_sidecar.get("quarantine_object_key") or "",
                sha256=existing_sidecar.get("sha256") or existing_user.get("sha256") or "",
                byte_size=int(existing_sidecar.get("byte_size") or 0),
                row_count=int(existing_sidecar.get("row_count") or 0),
                quarantine_row_count=int(existing_sidecar.get("quarantine_row_count") or 0),
                process_date=day,
                process_ts=existing_sidecar.get("process_ts") or process_ts,
                message=(
                    "processed object already present for same source_sha256 + "
                    "schema_version; skip upload"
                ),
            )
        raise RuntimeError(
            f"Refusing to overwrite {processed_key}: existing source_sha256="
            f"{existing_sidecar.get('source_sha256')} schema="
            f"{existing_sidecar.get('schema_version')} != incoming "
            f"source_sha256={source_sha256} schema={SCHEMA_VERSION}"
        )

    canonical = transform_uci_csv_bytes(
        raw_bytes,
        station,
        source_file_name=source_file_name,
        source_object_key=raw_key,
        source_sha256=source_sha256,
        process_time=process_ts,
        source_system=SOURCE_SYSTEM,
    )
    dq = apply_data_quality(canonical)
    parquet_bytes = dataframe_to_parquet_bytes(dq.clean)
    digest = hashlib.sha256(parquet_bytes).hexdigest()
    byte_size = len(parquet_bytes)

    user_meta = {
        "station": station,
        "source_object_key": raw_key,
        "sha256": digest,
        "process_ts": process_ts,
    }

    put_bytes(
        minio,
        bkt,
        processed_key,
        parquet_bytes,
        content_type="application/octet-stream",
        metadata=user_meta,
    )

    if dq.quarantine_row_count > 0:
        q_bytes = dataframe_to_parquet_bytes(dq.quarantine)
        if object_exists(minio, bkt, quarantine_key):
            raise RuntimeError(
                f"Refusing to overwrite existing quarantine object {quarantine_key}"
            )
        put_bytes(
            minio,
            bkt,
            quarantine_key,
            q_bytes,
            content_type="application/octet-stream",
            metadata={
                "station": station,
                "sha256": hashlib.sha256(q_bytes).hexdigest(),
                "process_ts": process_ts,
            },
        )

    sidecar = {
        "station": station,
        "source_object_key": raw_key,
        "source_sha256": source_sha256,
        "source_file_name": source_file_name,
        "source_system": SOURCE_SYSTEM,
        "sha256": digest,
        "byte_size": byte_size,
        "row_count": len(dq.clean),
        "quarantine_row_count": dq.quarantine_row_count,
        "suspect_cap_row_count": dq.suspect_cap_row_count,
        "missing_pollutant_row_count": dq.missing_pollutant_row_count,
        "missing_weather_row_count": dq.missing_weather_row_count,
        "process_ts": process_ts,
        "run_ts": run_ts,
        "process_date": day,
        "schema_version": SCHEMA_VERSION,
        "object_key": processed_key,
        "quarantine_object_key": quarantine_key if dq.quarantine_row_count else None,
    }
    put_bytes(
        minio,
        bkt,
        meta_key,
        json.dumps(sidecar, indent=2, sort_keys=True).encode("utf-8"),
        content_type="application/json",
        metadata={"station": station, "sha256": digest, "process_ts": process_ts},
    )

    return ProcessResult(
        station=station,
        status="uploaded",
        raw_object_key=raw_key,
        processed_object_key=processed_key,
        meta_key=meta_key,
        quarantine_object_key=quarantine_key if dq.quarantine_row_count else "",
        sha256=digest,
        byte_size=byte_size,
        row_count=len(dq.clean),
        quarantine_row_count=dq.quarantine_row_count,
        process_date=day,
        process_ts=process_ts,
        message="uploaded processed Parquet + sidecar metadata",
    )


def _normalize_day(process_date: str | date | None) -> str:
    if process_date is None:
        return datetime.now(timezone.utc).date().isoformat()
    if isinstance(process_date, date):
        return process_date.isoformat()
    return process_date


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
