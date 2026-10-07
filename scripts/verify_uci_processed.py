#!/usr/bin/env python3
"""Verify processed Parquet for one station (P4-12).

Checks:
- processed object + sidecar exist
- canonical columns present
- row_count ≈ raw CSV row count (raw rows - quarantine)
- raw object still present / unchanged sha256
- sidecar sha256 matches Parquet bytes
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.processing.schema import CANONICAL_OUTPUT_COLUMNS  # noqa: E402
from src.processing.uci_to_processed import (  # noqa: E402
    build_meta_key,
    build_processed_key,
    resolve_latest_raw_object_key,
)
from src.utils.minio_client import (  # noqa: E402
    get_bucket,
    get_minio_client,
    get_object_bytes,
    get_object_metadata,
    object_exists,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify UCI processed Parquet in MinIO")
    parser.add_argument("--station", default="Wanshouxigong")
    parser.add_argument("--process-date", required=True, help="process_date=YYYY-MM-DD")
    parser.add_argument(
        "--raw-key",
        default=None,
        help="Optional raw object key (default: latest for station)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Optional path to write JSON evidence",
    )
    args = parser.parse_args()

    client = get_minio_client()
    bucket = get_bucket()
    station = args.station
    processed_key = build_processed_key(station, args.process_date)
    meta_key = build_meta_key(processed_key)
    raw_key = args.raw_key or resolve_latest_raw_object_key(
        station, client=client, bucket=bucket
    )

    errors: list[str] = []

    if not object_exists(client, bucket, processed_key):
        errors.append(f"missing processed object: {processed_key}")
    if not object_exists(client, bucket, meta_key):
        errors.append(f"missing sidecar: {meta_key}")
    if not object_exists(client, bucket, raw_key):
        errors.append(f"missing raw object: {raw_key}")

    parquet_bytes = b""
    sidecar: dict = {}
    raw_bytes = b""
    raw_meta: dict = {}
    if not errors:
        parquet_bytes = get_object_bytes(client, bucket, processed_key)
        sidecar = json.loads(get_object_bytes(client, bucket, meta_key))
        raw_bytes = get_object_bytes(client, bucket, raw_key)
        raw_meta = get_object_metadata(client, bucket, raw_key)

    parquet_sha = hashlib.sha256(parquet_bytes).hexdigest() if parquet_bytes else ""
    raw_sha = hashlib.sha256(raw_bytes).hexdigest() if raw_bytes else ""
    expected_raw_sha = raw_meta.get("sha256") or raw_sha

    df = pd.DataFrame()
    if parquet_bytes:
        df = pd.read_parquet(io.BytesIO(parquet_bytes))
        missing_cols = [c for c in CANONICAL_OUTPUT_COLUMNS if c not in df.columns]
        if missing_cols:
            errors.append(f"missing canonical columns: {missing_cols}")

    raw_df = pd.DataFrame()
    if raw_bytes:
        raw_df = pd.read_csv(io.BytesIO(raw_bytes), na_values=["NA", "NaN", ""])

    quarantine_n = int(sidecar.get("quarantine_row_count") or 0)
    expected_rows = max(len(raw_df) - quarantine_n, 0) if len(raw_df) else None
    row_count_ok = expected_rows is None or len(df) == expected_rows

    if sidecar and parquet_sha and sidecar.get("sha256") != parquet_sha:
        errors.append(
            f"sidecar sha256 mismatch: {sidecar.get('sha256')} != {parquet_sha}"
        )
    if expected_raw_sha and raw_sha and expected_raw_sha != raw_sha:
        errors.append("raw object sha256 changed vs user-metadata")
    if not row_count_ok:
        errors.append(
            f"row_count mismatch: processed={len(df)} expected={expected_rows} "
            f"(raw={len(raw_df)} quarantine={quarantine_n})"
        )

    out = {
        "station": station,
        "process_date": args.process_date,
        "processed_object_key": processed_key,
        "meta_key": meta_key,
        "raw_object_key": raw_key,
        "parquet_sha256": parquet_sha,
        "sidecar_sha256": sidecar.get("sha256"),
        "raw_sha256": raw_sha,
        "raw_meta_sha256": raw_meta.get("sha256"),
        "row_count": int(len(df)),
        "raw_row_count": int(len(raw_df)),
        "quarantine_row_count": quarantine_n,
        "row_count_ok": row_count_ok,
        "canonical_columns_ok": not any("missing canonical" in e for e in errors),
        "raw_untouched": bool(raw_sha) and (not raw_meta.get("sha256") or raw_meta.get("sha256") == raw_sha),
        "errors": errors,
        "ok": len(errors) == 0,
    }

    text = json.dumps(out, indent=2, ensure_ascii=False)
    print(text)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
