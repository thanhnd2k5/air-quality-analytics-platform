"""Ingest operational DB delta batches into MinIO Raw (watermark CDC).

Phase 2 of docs/OPERATIONAL_DB_INGESTION_DESIGN.md.

Lake layout::

    raw/operational_db/year=YYYY/month=MM/batch_<wm_start>_to_<wm_end>_n<count>.json
    raw/operational_db/year=YYYY/month=MM/batch_....json.meta.json
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from minio import Minio

from src.ingestion.db_client import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_DB_PATH,
    DEFAULT_WATERMARK,
    SOURCE_IDENTIFIER,
    DeltaBatch,
    fetch_delta,
    validate_watermark,
)
from src.utils.minio_client import (
    get_bucket,
    get_minio_client,
    get_object_bytes,
    get_object_metadata,
    object_exists,
    put_bytes,
)

IngestStatus = Literal["uploaded", "skipped_identical", "empty"]

_SAFE_TS = re.compile(r"[^0-9T]")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_ts(value: str) -> str:
    """Turn '2016-01-01 00:00:00' into a path-safe token."""
    return _SAFE_TS.sub("", value.replace(" ", "T"))


def build_object_key(
    *,
    watermark_start: str,
    watermark_end: str,
    record_count: int,
) -> str:
    """Partition by batch end time; deterministic name for idempotent re-runs."""
    end = datetime.strptime(watermark_end, "%Y-%m-%d %H:%M:%S")
    year = end.year
    month = f"{end.month:02d}"
    name = (
        f"batch_{_safe_ts(watermark_start)}_to_{_safe_ts(watermark_end)}"
        f"_n{record_count}.json"
    )
    return f"raw/operational_db/year={year}/month={month}/{name}"


def build_meta_key(object_key: str) -> str:
    return f"{object_key}.meta.json"


def serialize_batch(batch: DeltaBatch) -> bytes:
    """Canonical JSON bytes for hashing + upload (sorted keys, stable)."""
    payload = {
        "source": SOURCE_IDENTIFIER,
        "watermark_start": batch.watermark_start,
        "watermark_end": batch.watermark_end,
        "record_count": batch.record_count,
        "records": batch.records,
    }
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


@dataclass(frozen=True)
class OperationalDbIngestResult:
    status: IngestStatus
    object_key: str
    meta_key: str
    sha256: str
    byte_size: int
    record_count: int
    watermark_start: str
    watermark_end: str | None
    ingestion_ts: str
    message: str
    db_path: str

    def to_dict(self) -> dict:
        return asdict(self)


def ingest_delta_batch_to_minio(
    *,
    watermark: str = DEFAULT_WATERMARK,
    batch_size: int = DEFAULT_BATCH_SIZE,
    db_path: Path | str | None = None,
    client: Minio | None = None,
    bucket: str | None = None,
    batch: DeltaBatch | None = None,
) -> OperationalDbIngestResult:
    """
    Fetch one delta batch (or use ``batch``) and upload JSON + sidecar to MinIO.

    Idempotency:
    - empty delta → status empty (no object)
    - object missing → upload
    - object exists with same sha256 → skip
    - object exists with different sha256 → fail (no overwrite)
    """
    path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    if batch is None:
        validate_watermark(watermark)
        delta = fetch_delta(watermark, batch_size=batch_size, db_path=path)
    else:
        delta = batch
    ingestion_ts = _utc_now_iso()

    if delta.record_count == 0 or delta.watermark_end is None:
        return OperationalDbIngestResult(
            status="empty",
            object_key="",
            meta_key="",
            sha256="",
            byte_size=0,
            record_count=0,
            watermark_start=delta.watermark_start,
            watermark_end=None,
            ingestion_ts=ingestion_ts,
            message="no rows with event_time_local > watermark",
            db_path=delta.db_path,
        )

    body = serialize_batch(delta)
    digest = hashlib.sha256(body).hexdigest()
    object_key = build_object_key(
        watermark_start=delta.watermark_start,
        watermark_end=delta.watermark_end,
        record_count=delta.record_count,
    )
    meta_key = build_meta_key(object_key)

    minio = client or get_minio_client()
    bkt = get_bucket(bucket)

    # S3 user-metadata is awkward with spaces; store path-safe forms there.
    user_meta = {
        "source": SOURCE_IDENTIFIER,
        "sha256": digest,
        "record_count": str(delta.record_count),
        "watermark_start": _safe_ts(delta.watermark_start),
        "watermark_end": _safe_ts(delta.watermark_end),
        "ingestion_ts": ingestion_ts,
    }

    if object_exists(minio, bkt, object_key):
        existing_meta = get_object_metadata(minio, bkt, object_key)
        existing_sha = existing_meta.get("sha256")
        if not existing_sha:
            remote = get_object_bytes(minio, bkt, object_key)
            existing_sha = hashlib.sha256(remote).hexdigest()

        if existing_sha == digest:
            return OperationalDbIngestResult(
                status="skipped_identical",
                object_key=object_key,
                meta_key=meta_key,
                sha256=digest,
                byte_size=len(body),
                record_count=delta.record_count,
                watermark_start=delta.watermark_start,
                watermark_end=delta.watermark_end,
                ingestion_ts=ingestion_ts,
                message="object already present with identical sha256; skip upload",
                db_path=delta.db_path,
            )

        raise RuntimeError(
            f"Refusing to overwrite {object_key}: existing sha256={existing_sha} "
            f"!= local sha256={digest}"
        )

    put_bytes(
        minio,
        bkt,
        object_key,
        body,
        content_type="application/json",
        metadata=user_meta,
    )

    sidecar = {
        "source_identifier": SOURCE_IDENTIFIER,
        "object_key": object_key,
        "record_count": delta.record_count,
        "source_sha256": digest,
        "byte_size": len(body),
        "watermark_start": delta.watermark_start,
        "watermark_end": delta.watermark_end,
        "ingestion_ts": ingestion_ts,
        "db_path": delta.db_path,
        "batch_size_limit": delta.batch_size_limit,
    }
    try:
        put_bytes(
            minio,
            bkt,
            meta_key,
            json.dumps(sidecar, indent=2, sort_keys=True, ensure_ascii=True).encode("utf-8"),
            content_type="application/json",
            metadata={
                "source": SOURCE_IDENTIFIER,
                "sha256": digest,
                "ingestion_ts": ingestion_ts,
            },
        )
    except Exception:
        # Avoid orphan data object without sidecar when meta upload fails.
        try:
            minio.remove_object(bkt, object_key)
        except Exception:  # noqa: BLE001 — best-effort cleanup
            pass
        raise

    return OperationalDbIngestResult(
        status="uploaded",
        object_key=object_key,
        meta_key=meta_key,
        sha256=digest,
        byte_size=len(body),
        record_count=delta.record_count,
        watermark_start=delta.watermark_start,
        watermark_end=delta.watermark_end,
        ingestion_ts=ingestion_ts,
        message="uploaded operational_db delta batch + sidecar metadata",
        db_path=delta.db_path,
    )
