#!/usr/bin/env python3
"""CLI smoke: ingest one (or all) UCI station CSV(s) into MinIO Raw.

Examples:
    python scripts/ingest_uci_station.py --station Wanshouxigong
    python scripts/ingest_uci_station.py --all
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

from src.ingestion.uci_to_minio import ingest_station_to_minio  # noqa: E402
from src.validation.uci_raw import load_inventory  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest UCI raw station CSV → MinIO")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--station", help="Station name, e.g. Wanshouxigong")
    group.add_argument("--all", action="store_true", help="Ingest all stations in inventory")
    parser.add_argument(
        "--ingestion-date",
        default=None,
        help="Override ingestion_date=YYYY-MM-DD (default: UTC today)",
    )
    parser.add_argument(
        "--inventory",
        default=None,
        help="Path to file_inventory.csv",
    )
    parser.add_argument(
        "--uci-dir",
        default=None,
        help="Directory containing PRSA_Data_*.csv",
    )
    args = parser.parse_args()

    inventory_path = Path(args.inventory) if args.inventory else None
    uci_dir = Path(args.uci_dir) if args.uci_dir else None

    if args.all:
        stations = sorted(load_inventory(inventory_path).keys())
    else:
        stations = [args.station]

    results = []
    exit_code = 0
    for station in stations:
        try:
            result = ingest_station_to_minio(
                station,
                inventory_path=inventory_path,
                uci_raw_dir=uci_dir,
                ingestion_date=args.ingestion_date,
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
