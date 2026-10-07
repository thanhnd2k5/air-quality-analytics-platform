#!/usr/bin/env python3
"""CLI: process Open-Meteo raw MinIO JSON → processed om_* Parquet.

Examples:
    python scripts/process_openmeteo_station.py --station Wanshouxigong
    python scripts/process_openmeteo_station.py --all
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

from src.processing.openmeteo_to_processed import (  # noqa: E402
    list_reference_stations,
    process_openmeteo_station,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Process Open-Meteo raw → om_* Parquet")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--station", help="Station name")
    group.add_argument("--all", action="store_true")
    parser.add_argument("--process-date", default=None)
    parser.add_argument(
        "--ingestion-date",
        default=None,
        help="Raw partition ingestion_date=YYYY-MM-DD (default: latest)",
    )
    parser.add_argument("--manifest", default=None)
    args = parser.parse_args()

    stations = list_reference_stations() if args.all else [args.station]
    exit_code = 0
    results: list[dict] = []

    for station in stations:
        try:
            result = process_openmeteo_station(
                station,
                process_date=args.process_date,
                ingestion_date=args.ingestion_date,
            )
            payload = result.to_dict()
            results.append(payload)
            print(json.dumps(payload, ensure_ascii=False))
        except Exception as exc:  # noqa: BLE001
            exit_code = 1
            err = {"station": station, "status": "failed", "message": str(exc)}
            results.append(err)
            print(json.dumps(err, ensure_ascii=False), file=sys.stderr)

    if args.manifest:
        path = Path(args.manifest)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            for row in results:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    if len(stations) > 1:
        print(
            json.dumps(
                {
                    "station_count": len(stations),
                    "uploaded": sum(1 for r in results if r.get("status") == "uploaded"),
                    "skipped_identical": sum(
                        1 for r in results if r.get("status") == "skipped_identical"
                    ),
                    "failed": sum(1 for r in results if r.get("status") == "failed"),
                },
                indent=2,
            )
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
