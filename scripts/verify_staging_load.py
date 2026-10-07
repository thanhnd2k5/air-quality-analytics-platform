#!/usr/bin/env python3
"""Reconcile PostgreSQL staging against processed Parquet sidecars.

Writes a JSON report (default artifacts/staging/reconcile.json).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from src.reference.stations import list_station_names  # noqa: E402
from src.staging.load import connect  # noqa: E402
from src.staging.reconcile import reconcile  # noqa: E402
from src.staging.schema import (  # noqa: E402
    EXPECTED_STATION_COUNT,
    OM_PROCESSED_PREFIX,
    UCI_PROCESSED_PREFIX,
    select_latest_processed_key,
)
from src.utils.minio_client import get_bucket, get_minio_client, list_object_names  # noqa: E402


def minio_fingerprints(stations: list[str]) -> dict:
    client = get_minio_client()
    bucket = get_bucket()
    objects = []
    for station in stations:
        for prefix in (
            UCI_PROCESSED_PREFIX.format(station=station),
            OM_PROCESSED_PREFIX.format(station=station),
        ):
            names = list_object_names(client, bucket, prefix=prefix)
            if not names:
                continue
            key = select_latest_processed_key(names)
            stat = client.stat_object(bucket, key)
            objects.append(
                {
                    "object_key": key,
                    "size": stat.size,
                    "etag": stat.etag,
                    "last_modified": stat.last_modified.isoformat()
                    if stat.last_modified is not None
                    else None,
                }
            )
    return {"bucket": bucket, "objects": objects}


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile staging tables to processed sources")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--station", help="Single station")
    group.add_argument("--all", action="store_true", help="All stations in stations.csv")
    parser.add_argument(
        "--output",
        default=None,
        help="JSON output path (default artifacts/staging/reconcile.json or fingerprint path)",
    )
    parser.add_argument(
        "--fingerprint-only",
        action="store_true",
        help="Record MinIO processed object size/etag only (no Postgres)",
    )
    args = parser.parse_args()

    stations = list_station_names() if args.all else [args.station]
    if args.fingerprint_only:
        report = minio_fingerprints(stations)
        default_name = "minio_fingerprint.json"
        exit_code = 0
    else:
        conn = connect()
        try:
            report = reconcile(
                conn,
                stations,
                expect_full=args.all and len(stations) == EXPECTED_STATION_COUNT,
            )
        finally:
            conn.close()
        report["minio_fingerprint"] = minio_fingerprints(stations)
        default_name = "reconcile.json"
        exit_code = 0 if report["ok"] else 1

    out = Path(args.output) if args.output else ROOT / "artifacts" / "staging" / default_name
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(out), "ok": report.get("ok", True), "errors": report.get("errors", [])}, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
