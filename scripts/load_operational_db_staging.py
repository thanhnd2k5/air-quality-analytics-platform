#!/usr/bin/env python3
"""CLI: load operational_db CDC MinIO batches into staging.air_quality_hourly.

Examples:
    py scripts/load_operational_db_staging.py
    py scripts/load_operational_db_staging.py --object-key raw/operational_db/year=2016/month=01/batch_....json
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

from src.staging.operational_db_load import (  # noqa: E402
    list_cdc_batch_keys,
    load_cdc_batches,
    staging_operational_watermark,
)


def emit(payload: dict, *, stream=sys.stdout) -> None:
    print(json.dumps(payload, ensure_ascii=True, indent=2, default=str), file=stream)


def main() -> int:
    parser = argparse.ArgumentParser(description="Load operational_db CDC batches → staging")
    parser.add_argument(
        "--object-key",
        action="append",
        default=None,
        help="MinIO object key (repeatable). Default: all under raw/operational_db/",
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="List CDC batch keys and current staging watermark; do not load",
    )
    args = parser.parse_args()

    try:
        if args.list_only:
            keys = list_cdc_batch_keys()
            emit(
                {
                    "status": "list_only_ok",
                    "batch_count": len(keys),
                    "object_keys": keys,
                    "staging_watermark": staging_operational_watermark(),
                }
            )
            return 0

        results = load_cdc_batches(args.object_key)
        emit(
            {
                "status": "ok",
                "batch_count": len(results),
                "loaded": sum(1 for r in results if r.status == "loaded"),
                "skipped": sum(1 for r in results if r.status == "skipped_identical"),
                "empty": sum(1 for r in results if r.status == "empty"),
                "staging_watermark": staging_operational_watermark(),
                "results": [r.to_dict() for r in results],
            }
        )
        return 0
    except Exception as exc:  # noqa: BLE001
        emit({"status": "failed", "message": str(exc)}, stream=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
