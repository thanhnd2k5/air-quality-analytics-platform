"""Ingest Open-Meteo historical weather JSON into MinIO Raw zone (Phase 5b)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from minio import Minio

from src.ingestion.openmeteo_client import (
    DEFAULT_HOURLY_VARIABLES,
    DEFAULT_TIMEZONE,
    SOURCE_IDENTIFIER,
    fetch_historical_weather,
)
from src.reference.stations import get_station, list_station_names
from src.utils.minio_client import (
    get_bucket,
    get_minio_client,
    get_object_bytes,
    get_object_metadata,
    object_exists,
    put_bytes,
)

IngestStatus = Literal["uploaded", "skipped_identical", "failed"]

# UCI PRSA coverage (DATA_GUIDE / inventory)
DEFAULT_START_DATE = "2013-03-01"
DEFAULT_END_DATE = "2017-02-28"


@dataclass(frozen=True)
class OpenMeteoIngestResult:
    station: str
    status: IngestStatus
    object_key: str
    meta_key: str
    sha256: str
    byte_size: int
    ingestion_date: str
    ingestion_ts: str
    start_date: str
    end_date: str
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_day(value: str | date | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def build_object_key(
    station: str,
    start_date: str,
    end_date: str,
    ingestion_date: str | date | None = None,
) -> str:
    day = _normalize_day(ingestion_date)
    file_name = f"historical_{start_date}_{end_date}.json"
    return (
        f"raw/openmeteo/historical_weather/station={station}/"
        f"ingestion_date={day}/{file_name}"
    )


def build_meta_key(object_key: str) -> str:
    return f"{object_key}.meta.json"


def request_fingerprint(
    *,
    station: str,
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    timezone: str,
    hourly: tuple[str, ...] | list[str],
) -> str:
    payload = {
        "station": station,
        "latitude": round(latitude, 6),
        "longitude": round(longitude, 6),
        "start_date": start_date,
        "end_date": end_date,
        "timezone": timezone,
        "hourly": list(hourly),
        "temperature_unit": "celsius",
        "wind_speed_unit": "ms",
        "precipitation_unit": "mm",
        "source": SOURCE_IDENTIFIER,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def iter_date_chunks(
    start_date: str,
    end_date: str,
    *,
    chunk_months: int = 12,
) -> list[tuple[str, str]]:
    """Split [start, end] into inclusive calendar-year chunks (API safety).

    ``chunk_months`` other than 12 is accepted for tests but still uses year boundaries
    when == 12; otherwise uses fixed-length month steps.
    """
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    if end < start:
        raise ValueError(f"end_date {end_date} < start_date {start_date}")

    chunks: list[tuple[str, str]] = []
    if chunk_months == 12:
        cursor = start
        while cursor <= end:
            chunk_end = min(date(cursor.year, 12, 31), end)
            chunks.append((cursor.isoformat(), chunk_end.isoformat()))
            cursor = date(cursor.year + 1, 1, 1)
        return chunks

    # Fixed month steps (approx): advance chunk_months from cursor
    cursor = start
    while cursor <= end:
        month_index = cursor.year * 12 + (cursor.month - 1) + chunk_months
        next_year, next_month0 = divmod(month_index, 12)
        next_start = date(next_year, next_month0 + 1, 1)
        chunk_end = min(next_start - timedelta(days=1), end)
        chunks.append((cursor.isoformat(), chunk_end.isoformat()))
        cursor = chunk_end + timedelta(days=1)
    return chunks


def ingest_openmeteo_station_to_minio(
    station: str,
    *,
    start_date: str = DEFAULT_START_DATE,
    end_date: str = DEFAULT_END_DATE,
    client: Minio | None = None,
    bucket: str | None = None,
    ingestion_date: str | date | None = None,
    timezone: str = DEFAULT_TIMEZONE,
    chunk_months: int = 12,
) -> list[OpenMeteoIngestResult]:
    """
    Fetch Open-Meteo for one station over [start_date, end_date], chunked, upload raw JSON.

    Idempotency per object key:
    - missing → upload
    - same sha256 → skip
    - different sha256 → fail (no overwrite)
    """
    ref = get_station(station)
    minio = client or get_minio_client()
    bkt = get_bucket(bucket)
    day = _normalize_day(ingestion_date)
    results: list[OpenMeteoIngestResult] = []

    for chunk_start, chunk_end in iter_date_chunks(start_date, end_date, chunk_months=chunk_months):
        results.append(
            _ingest_one_chunk(
                station=ref.station_name,
                latitude=ref.latitude,
                longitude=ref.longitude,
                start_date=chunk_start,
                end_date=chunk_end,
                ingestion_date=day,
                timezone=timezone,
                client=minio,
                bucket=bkt,
            )
        )
    return results


def _ingest_one_chunk(
    *,
    station: str,
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    ingestion_date: str,
    timezone: str,
    client: Minio,
    bucket: str,
) -> OpenMeteoIngestResult:
    object_key = build_object_key(station, start_date, end_date, ingestion_date)
    meta_key = build_meta_key(object_key)
    ingestion_ts = _utc_now_iso()
    fingerprint = request_fingerprint(
        station=station,
        latitude=latitude,
        longitude=longitude,
        start_date=start_date,
        end_date=end_date,
        timezone=timezone,
        hourly=DEFAULT_HOURLY_VARIABLES,
    )

    # Skip before API call when the same logical request is already stored.
    # Open-Meteo JSON includes volatile fields (e.g. generationtime_ms), so raw
    # sha256 can differ across identical requests.
    if object_exists(client, bucket, object_key):
        existing_fp = None
        existing_sha = ""
        existing_size = 0
        if object_exists(client, bucket, meta_key):
            sidecar_existing = json.loads(get_object_bytes(client, bucket, meta_key))
            existing_fp = sidecar_existing.get("request_fingerprint")
            existing_sha = sidecar_existing.get("sha256") or ""
            existing_size = int(sidecar_existing.get("byte_size") or 0)
        if not existing_fp:
            existing_fp = get_object_metadata(client, bucket, object_key).get(
                "request_fingerprint"
            )
        if existing_fp == fingerprint:
            return OpenMeteoIngestResult(
                station=station,
                status="skipped_identical",
                object_key=object_key,
                meta_key=meta_key,
                sha256=existing_sha,
                byte_size=existing_size,
                ingestion_date=ingestion_date,
                ingestion_ts=ingestion_ts,
                start_date=start_date,
                end_date=end_date,
                message=(
                    "object already present with identical request_fingerprint; "
                    "skip API fetch + upload"
                ),
            )
        raise RuntimeError(
            f"Refusing to overwrite {object_key}: existing request_fingerprint="
            f"{existing_fp} != incoming {fingerprint}"
        )

    fetch = fetch_historical_weather(
        station=station,
        latitude=latitude,
        longitude=longitude,
        start_date=start_date,
        end_date=end_date,
        timezone=timezone,
    )
    raw = fetch.raw_bytes
    digest = hashlib.sha256(raw).hexdigest()

    user_meta = {
        "station": station,
        "sha256": digest,
        "ingestion_ts": ingestion_ts,
        "request_fingerprint": fingerprint,
    }

    put_bytes(
        client,
        bucket,
        object_key,
        raw,
        content_type="application/json",
        metadata=user_meta,
    )

    sidecar = {
        **fetch.meta.to_dict(),
        "sha256": digest,
        "byte_size": len(raw),
        "ingestion_ts": ingestion_ts,
        "ingestion_date": ingestion_date,
        "source_identifier": SOURCE_IDENTIFIER,
        "object_key": object_key,
        "request_fingerprint": fingerprint,
        "coordinate_status": get_station(station).coordinate_status,
    }
    put_bytes(
        client,
        bucket,
        meta_key,
        json.dumps(sidecar, indent=2, sort_keys=True).encode("utf-8"),
        content_type="application/json",
        metadata={"station": station, "sha256": digest, "ingestion_ts": ingestion_ts},
    )

    return OpenMeteoIngestResult(
        station=station,
        status="uploaded",
        object_key=object_key,
        meta_key=meta_key,
        sha256=digest,
        byte_size=len(raw),
        ingestion_date=ingestion_date,
        ingestion_ts=ingestion_ts,
        start_date=start_date,
        end_date=end_date,
        message="uploaded Open-Meteo raw JSON + sidecar metadata",
    )


def list_openmeteo_stations() -> list[str]:
    return list_station_names()
