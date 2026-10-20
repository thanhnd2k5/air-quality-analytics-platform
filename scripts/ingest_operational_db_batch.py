#!/usr/bin/env python3
"""CLI smoke: watermark CDC extract from operational SQLite -> MinIO Raw.

Examples:
    py scripts/ingest_operational_db_batch.py --fetch-only
    py scripts/ingest_operational_db_batch.py --watermark "2015-12-31 23:00:00" --batch-size 1000
    py scripts/ingest_operational_db_batch.py --watermark "2016-06-30 23:00:00"
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

from src.ingestion.db_client import (  # noqa: E402
    DEFAULT_BATCH_SIZE,
    DEFAULT_DB_PATH,
    DEFAULT_WATERMARK,
    fetch_delta,
    peek_max_event_time,
)
from src.ingestion.db_to_minio import ingest_delta_batch_to_minio  # noqa: E402


def emit(payload: dict, *, stream=sys.stdout) -> None:
    print(json.dumps(payload, ensure_ascii=True, indent=2), file=stream)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingest one operational_db watermark CDC batch -> MinIO"
    )
    parser.add_argument(
        "--watermark",
        default=DEFAULT_WATERMARK,
        help=f"Exclusive lower bound event_time_local (default: {DEFAULT_WATERMARK})",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Max rows per batch (default: {DEFAULT_BATCH_SIZE})",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Path to prsa_operational.db",
    )
    parser.add_argument(
        "--fetch-only",
        action="store_true",
        help="Only query SQLite and print summary (no MinIO upload)",
    )
    args = parser.parse_args()

    try:
        batch = fetch_delta(
            args.watermark,
            batch_size=args.batch_size,
            db_path=args.db_path,
        )
    except Exception as exc:  # noqa: BLE001
        emit({"status": "failed", "message": str(exc)}, stream=sys.stderr)
        return 1

    if args.fetch_only:
        sample = batch.records[0] if batch.records else None
        emit(
            {
                "status": "fetch_only_ok",
                "record_count": batch.record_count,
                "watermark_start": batch.watermark_start,
                "watermark_end": batch.watermark_end,
                "db_max_event_time": peek_max_event_time(args.db_path),
                "db_path": batch.db_path,
                "sample_first_row": sample,
            }
        )
        return 0

    try:
        result = ingest_delta_batch_to_minio(
            watermark=args.watermark,
            batch_size=args.batch_size,
            db_path=args.db_path,
            batch=batch,
        )
    except Exception as exc:  # noqa: BLE001
        emit({"status": "failed", "message": str(exc)}, stream=sys.stderr)
        return 1

    emit(result.to_dict())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
