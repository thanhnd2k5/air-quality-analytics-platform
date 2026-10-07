"""Ingest UCI raw station CSVs into MinIO Raw zone (Phase 3)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

from minio import Minio

from src.utils.minio_client import (
    get_bucket,
    get_minio_client,
    get_object_bytes,
    get_object_metadata,
    object_exists,
    put_bytes,
    put_file,
)
from src.validation.uci_raw import validate_uci_raw_file


SOURCE_IDENTIFIER = "uci_prsa"

IngestStatus = Literal["uploaded", "skipped_identical", "failed"]


@dataclass(frozen=True)
class IngestResult:
    station: str
    status: IngestStatus
    object_key: str
    meta_key: str
    sha256: str
    byte_size: int
    ingestion_date: str
    ingestion_ts: str
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def build_object_key(
    station: str,
    file_name: str,
    ingestion_date: str | date | None = None,
) -> str:
    if ingestion_date is None:
        day = datetime.now(timezone.utc).date().isoformat()
    elif isinstance(ingestion_date, date):
        day = ingestion_date.isoformat()
    else:
        day = ingestion_date
    return f"raw/uci/air_quality/station={station}/ingestion_date={day}/{file_name}"


def build_meta_key(object_key: str) -> str:
    return f"{object_key}.meta.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ingest_station_to_minio(
    station: str,
    *,
    client: Minio | None = None,
    bucket: str | None = None,
    inventory_path: Path | None = None,
    uci_raw_dir: Path | None = None,
    ingestion_date: str | date | None = None,
) -> IngestResult:
    """
    Validate (light) then upload raw CSV + sidecar metadata.

    Idempotency:
    - object missing → upload
    - object exists with same sha256 → skip (success)
    - object exists with different sha256 → fail (no overwrite)
    """
    validation = validate_uci_raw_file(
        station, inventory_path=inventory_path, uci_raw_dir=uci_raw_dir
    )
    if not validation.ok:
        raise ValueError(validation.message)

    path = validation.source_path
    digest, byte_size = sha256_file(path)
    object_key = build_object_key(station, validation.file_name, ingestion_date)
    meta_key = build_meta_key(object_key)
    ingestion_ts = _utc_now_iso()
    day = object_key.split("ingestion_date=")[1].split("/")[0]

    minio = client or get_minio_client()
    bkt = get_bucket(bucket)

    user_meta = {
        "station": station,
        "source_file": validation.file_name,
        "sha256": digest,
        "ingestion_ts": ingestion_ts,
    }

    if object_exists(minio, bkt, object_key):
        existing_meta = get_object_metadata(minio, bkt, object_key)
        existing_sha = existing_meta.get("sha256")
        if not existing_sha:
            # Fall back to hashing remote bytes (rare: object without metadata)
            remote = get_object_bytes(minio, bkt, object_key)
            existing_sha = hashlib.sha256(remote).hexdigest()

        if existing_sha == digest:
            return IngestResult(
                station=station,
                status="skipped_identical",
                object_key=object_key,
                meta_key=meta_key,
                sha256=digest,
                byte_size=byte_size,
                ingestion_date=day,
                ingestion_ts=ingestion_ts,
                message="object already present with identical sha256; skip upload",
            )

        raise RuntimeError(
            f"Refusing to overwrite {object_key}: existing sha256={existing_sha} "
            f"!= local sha256={digest}"
        )

    put_file(
        minio,
        bkt,
        object_key,
        str(path),
        content_type="text/csv",
        metadata=user_meta,
    )

    sidecar = {
        "station": station,
        "source_file": validation.file_name,
        "source_relative_path": validation.relative_path,
        "sha256": digest,
        "byte_size": byte_size,
        "ingestion_ts": ingestion_ts,
        "ingestion_date": day,
        "source_identifier": SOURCE_IDENTIFIER,
        "object_key": object_key,
    }
    put_bytes(
        minio,
        bkt,
        meta_key,
        json.dumps(sidecar, indent=2, sort_keys=True).encode("utf-8"),
        content_type="application/json",
        metadata={"station": station, "sha256": digest, "ingestion_ts": ingestion_ts},
    )

    return IngestResult(
        station=station,
        status="uploaded",
        object_key=object_key,
        meta_key=meta_key,
        sha256=digest,
        byte_size=byte_size,
        ingestion_date=day,
        ingestion_ts=ingestion_ts,
        message="uploaded raw CSV + sidecar metadata",
    )
