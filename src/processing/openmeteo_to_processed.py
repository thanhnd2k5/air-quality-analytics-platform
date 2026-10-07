"""Process Open-Meteo raw MinIO JSON into processed om_* Parquet (Phase 5b)."""

from __future__ import annotations

import hashlib
import io
import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from typing import Any, Literal

import pandas as pd
from minio import Minio

from src.ingestion.openmeteo_client import hourly_to_records
from src.processing.openmeteo_schema import (
    CANONICAL_OUTPUT_COLUMNS,
    OM_HOURLY_TO_CANONICAL,
    SCHEMA_VERSION,
    SOURCE_SYSTEM,
)
from src.reference.stations import list_station_names
from src.utils.minio_client import (
    get_bucket,
    get_minio_client,
    get_object_bytes,
    get_object_metadata,
    list_object_names,
    object_exists,
    put_bytes,
)

ProcessStatus = Literal["uploaded", "skipped_identical", "failed"]

_RAW_PREFIX = "raw/openmeteo/historical_weather/station={station}/"
_INGESTION_DATE_RE = re.compile(r"ingestion_date=(\d{4}-\d{2}-\d{2})")


@dataclass(frozen=True)
class OpenMeteoProcessResult:
    station: str
    status: ProcessStatus
    raw_object_keys: list[str]
    processed_object_key: str
    meta_key: str
    sha256: str
    byte_size: int
    row_count: int
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
        f"processed/weather/openmeteo/station={station}/"
        f"process_date={day}/{slug}_hourly.parquet"
    )


def build_meta_key(processed_object_key: str) -> str:
    if processed_object_key.endswith(".parquet"):
        return processed_object_key[: -len(".parquet")] + ".meta.json"
    return f"{processed_object_key}.meta.json"


def list_raw_openmeteo_keys(
    station: str,
    *,
    client: Minio | None = None,
    bucket: str | None = None,
) -> list[str]:
    minio = client or get_minio_client()
    bkt = get_bucket(bucket)
    prefix = _RAW_PREFIX.format(station=station)
    names = list_object_names(minio, bkt, prefix=prefix)
    jsons = [
        n
        for n in names
        if n.endswith(".json") and not n.endswith(".meta.json")
    ]
    if not jsons:
        raise FileNotFoundError(f"No Open-Meteo raw JSON under prefix {prefix}")

    def sort_key(object_name: str) -> tuple[str, str]:
        match = _INGESTION_DATE_RE.search(object_name)
        day = match.group(1) if match else ""
        return (day, object_name)

    return sorted(jsons, key=sort_key)


def transform_openmeteo_json_bytes(
    data: bytes,
    station: str,
    *,
    source_object_key: str,
    source_sha256: str,
    process_time: str,
) -> pd.DataFrame:
    payload = json.loads(data.decode("utf-8"))
    rows = hourly_to_records(payload)
    if not rows:
        return pd.DataFrame(columns=list(CANONICAL_OUTPUT_COLUMNS))

    df = pd.DataFrame(rows)
    df["event_time_local"] = pd.to_datetime(df["time"])
    df["station_name"] = station

    for src, dst in OM_HOURLY_TO_CANONICAL.items():
        if src in df.columns:
            df[dst] = pd.to_numeric(df[src], errors="coerce")
        else:
            df[dst] = pd.NA

    df["source_object_key"] = source_object_key
    df["source_system"] = SOURCE_SYSTEM
    df["source_sha256"] = source_sha256
    df["process_time"] = process_time
    return df[list(CANONICAL_OUTPUT_COLUMNS)]


def dataframe_to_parquet_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_parquet(buf, index=False, engine="pyarrow")
    return buf.getvalue()


def process_openmeteo_station(
    station: str,
    *,
    client: Minio | None = None,
    bucket: str | None = None,
    process_date: str | date | None = None,
    raw_object_keys: list[str] | None = None,
) -> OpenMeteoProcessResult:
    """
    Resolve all raw OM JSON chunks for a station → one processed om_* Parquet.

    Idempotency: same combined source fingerprint + schema_version → skip.
    """
    minio = client or get_minio_client()
    bkt = get_bucket(bucket)
    day = _normalize_day(process_date)
    process_ts = f"{day}T00:00:00Z"
    run_ts = _utc_now_iso()

    raw_keys = raw_object_keys or list_raw_openmeteo_keys(station, client=minio, bucket=bkt)
    frames: list[pd.DataFrame] = []
    source_digests: list[str] = []

    for raw_key in raw_keys:
        raw_bytes = get_object_bytes(minio, bkt, raw_key)
        source_sha = hashlib.sha256(raw_bytes).hexdigest()
        raw_meta = get_object_metadata(minio, bkt, raw_key)
        if raw_meta.get("sha256"):
            source_sha = raw_meta["sha256"]
        source_digests.append(source_sha)
        frames.append(
            transform_openmeteo_json_bytes(
                raw_bytes,
                station,
                source_object_key=raw_key,
                source_sha256=source_sha,
                process_time=process_ts,
            )
        )

    combined_source = hashlib.sha256(
        "|".join(sorted(source_digests)).encode("utf-8")
    ).hexdigest()

    processed_key = build_processed_key(station, day)
    meta_key = build_meta_key(processed_key)

    if object_exists(minio, bkt, processed_key):
        existing_sidecar: dict[str, Any] = {}
        if object_exists(minio, bkt, meta_key):
            existing_sidecar = json.loads(get_object_bytes(minio, bkt, meta_key))
        existing_user = get_object_metadata(minio, bkt, processed_key)
        same_source = existing_sidecar.get("source_sha256") == combined_source
        same_schema = existing_sidecar.get("schema_version") == SCHEMA_VERSION
        if same_source and same_schema:
            return OpenMeteoProcessResult(
                station=station,
                status="skipped_identical",
                raw_object_keys=raw_keys,
                processed_object_key=processed_key,
                meta_key=meta_key,
                sha256=existing_sidecar.get("sha256") or existing_user.get("sha256") or "",
                byte_size=int(existing_sidecar.get("byte_size") or 0),
                row_count=int(existing_sidecar.get("row_count") or 0),
                process_date=day,
                process_ts=existing_sidecar.get("process_ts") or process_ts,
                message=(
                    "processed OM object already present for same source_sha256 + "
                    "schema_version; skip upload"
                ),
            )
        raise RuntimeError(
            f"Refusing to overwrite {processed_key}: existing source_sha256="
            f"{existing_sidecar.get('source_sha256')} schema="
            f"{existing_sidecar.get('schema_version')} != incoming "
            f"source_sha256={combined_source} schema={SCHEMA_VERSION}"
        )

    if not frames:
        raise RuntimeError(f"No frames built for station {station}")

    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset=["station_name", "event_time_local"], keep="last")
    df = df.sort_values("event_time_local").reset_index(drop=True)
    # Multi-chunk lineage: keep first raw key column values; sidecar lists all keys
    if len(raw_keys) > 1:
        df["source_object_key"] = ",".join(raw_keys)
        df["source_sha256"] = combined_source

    parquet_bytes = dataframe_to_parquet_bytes(df)
    digest = hashlib.sha256(parquet_bytes).hexdigest()
    byte_size = len(parquet_bytes)

    put_bytes(
        minio,
        bkt,
        processed_key,
        parquet_bytes,
        content_type="application/octet-stream",
        metadata={
            "station": station,
            "source_object_key": raw_keys[0][:200],
            "sha256": digest,
            "process_ts": process_ts,
        },
    )

    sidecar = {
        "station": station,
        "source_object_keys": raw_keys,
        "source_sha256": combined_source,
        "source_system": SOURCE_SYSTEM,
        "sha256": digest,
        "byte_size": byte_size,
        "row_count": len(df),
        "process_ts": process_ts,
        "run_ts": run_ts,
        "process_date": day,
        "schema_version": SCHEMA_VERSION,
        "object_key": processed_key,
    }
    put_bytes(
        minio,
        bkt,
        meta_key,
        json.dumps(sidecar, indent=2, sort_keys=True).encode("utf-8"),
        content_type="application/json",
        metadata={"station": station, "sha256": digest, "process_ts": process_ts},
    )

    return OpenMeteoProcessResult(
        station=station,
        status="uploaded",
        raw_object_keys=raw_keys,
        processed_object_key=processed_key,
        meta_key=meta_key,
        sha256=digest,
        byte_size=byte_size,
        row_count=len(df),
        process_date=day,
        process_ts=process_ts,
        message="uploaded Open-Meteo processed Parquet + sidecar metadata",
    )


def list_reference_stations() -> list[str]:
    return list_station_names()


def _normalize_day(process_date: str | date | None) -> str:
    if process_date is None:
        return datetime.now(timezone.utc).date().isoformat()
    if isinstance(process_date, date):
        return process_date.isoformat()
    return process_date


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
