#!/usr/bin/env python3
"""CLI smoke: process one (or all) UCI station(s) from MinIO Raw → Processed Parquet.

Examples:
    python scripts/process_uci_station.py --station Wanshouxigong
    python scripts/process_uci_station.py --all
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow `python scripts/...` from repo root without installing the package
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.processing.uci_to_processed import (  # noqa: E402
    list_inventory_stations,
    process_station_to_processed,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Process UCI raw MinIO CSV → Processed Parquet")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--station", help="Station name, e.g. Wanshouxigong")
    group.add_argument("--all", action="store_true", help="Process all stations in inventory")
    parser.add_argument(
        "--process-date",
        default=None,
        help="Override process_date=YYYY-MM-DD (default: UTC today)",
    )
    parser.add_argument(
        "--raw-key",
        default=None,
        help="Override raw object key (single --station only)",
    )
    parser.add_argument(
        "--inventory",
        default=None,
        help="Path to file_inventory.csv (for --all)",
    )
    args = parser.parse_args()

    if args.raw_key and args.all:
        parser.error("--raw-key cannot be combined with --all")

    inventory_path = Path(args.inventory) if args.inventory else None

    if args.all:
        stations = list_inventory_stations(inventory_path)
    else:
        stations = [args.station]

    results = []
    exit_code = 0
    for station in stations:
        try:
            result = process_station_to_processed(
                station,
                process_date=args.process_date,
                raw_object_key=args.raw_key,
            )
            results.append(result.to_dict())
            print(json.dumps(result.to_dict(), ensure_ascii=False))
        except Exception as exc:  # noqa: BLE001 — CLI reports and continues for --all
            exit_code = 1
            err = {
                "station": station,
                "status": "failed",
                "message": str(exc),
            }
            results.append(err)
            print(json.dumps(err, ensure_ascii=False), file=sys.stderr)

    if len(stations) > 1:
        print(json.dumps({"summary_count": len(results), "results": results}, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
