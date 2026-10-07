#!/usr/bin/env python3
"""CLI: ingest Open-Meteo historical weather → MinIO Raw.

Examples:
    python scripts/ingest_openmeteo_station.py --station Wanshouxigong
    python scripts/ingest_openmeteo_station.py --all
    python scripts/ingest_openmeteo_station.py --station Wanshouxigong --start 2015-01-01 --end 2015-01-31
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

from src.ingestion.openmeteo_to_minio import (  # noqa: E402
    DEFAULT_END_DATE,
    DEFAULT_START_DATE,
    ingest_openmeteo_station_to_minio,
    list_openmeteo_stations,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest Open-Meteo → MinIO Raw")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--station", help="Station name, e.g. Wanshouxigong")
    group.add_argument("--all", action="store_true", help="Ingest all reference stations")
    parser.add_argument("--start", default=DEFAULT_START_DATE, help="start_date YYYY-MM-DD")
    parser.add_argument("--end", default=DEFAULT_END_DATE, help="end_date YYYY-MM-DD")
    parser.add_argument("--ingestion-date", default=None, help="Override ingestion_date")
    parser.add_argument(
        "--manifest",
        default=None,
        help="Optional JSONL path to append per-chunk results",
    )
    args = parser.parse_args()

    stations = list_openmeteo_stations() if args.all else [args.station]
    exit_code = 0
    all_results: list[dict] = []

    for station in stations:
        try:
            results = ingest_openmeteo_station_to_minio(
                station,
                start_date=args.start,
                end_date=args.end,
                ingestion_date=args.ingestion_date,
            )
            for r in results:
                payload = r.to_dict()
                all_results.append(payload)
                print(json.dumps(payload, ensure_ascii=False))
        except Exception as exc:  # noqa: BLE001
            exit_code = 1
            err = {"station": station, "status": "failed", "message": str(exc)}
            all_results.append(err)
            print(json.dumps(err, ensure_ascii=False), file=sys.stderr)

    if args.manifest:
        path = Path(args.manifest)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            for row in all_results:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    if len(stations) > 1 or len(all_results) > 1:
        summary = {
            "station_count": len(stations),
            "chunk_result_count": len(all_results),
            "uploaded": sum(1 for r in all_results if r.get("status") == "uploaded"),
            "skipped_identical": sum(
                1 for r in all_results if r.get("status") == "skipped_identical"
            ),
            "failed": sum(1 for r in all_results if r.get("status") == "failed"),
        }
        print(json.dumps(summary, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
