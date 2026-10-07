#!/usr/bin/env python3
"""Phase 5a POC: fetch Open-Meteo historical weather for one station × one month.

Example:
    python scripts/poc_openmeteo_fetch.py --station Wanshouxigong --start 2015-01-01 --end 2015-01-31
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ingestion.openmeteo_client import (  # noqa: E402
    fetch_historical_weather,
    hourly_to_records,
)
from src.reference.stations import get_station  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="POC: Open-Meteo Historical Weather fetch")
    parser.add_argument("--station", default="Wanshouxigong")
    parser.add_argument("--start", default="2015-01-01", help="start_date YYYY-MM-DD")
    parser.add_argument("--end", default="2015-01-31", help="end_date YYYY-MM-DD")
    parser.add_argument(
        "--out-dir",
        default="artifacts/openmeteo/poc",
        help="Directory for raw JSON + metadata",
    )
    parser.add_argument("--stations-csv", default=None)
    args = parser.parse_args()

    stations_csv = Path(args.stations_csv) if args.stations_csv else None
    ref = get_station(args.station, path=stations_csv)

    result = fetch_historical_weather(
        station=ref.station_name,
        latitude=ref.latitude,
        longitude=ref.longitude,
        start_date=args.start,
        end_date=args.end,
    )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{ref.station_name.lower()}_{args.start}_{args.end}"
    raw_path = out_dir / f"{stem}.json"
    meta_path = out_dir / f"{stem}.meta.json"
    summary_path = out_dir / f"{stem}.summary.json"
    coords_path = out_dir / "station_coords_check.json"

    raw_path.write_bytes(result.raw_bytes)
    meta_path.write_text(
        json.dumps(result.meta.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    records = hourly_to_records(result.payload)
    coords_payload = {
        "station": ref.station_name,
        "station_code": ref.station_code,
        "requested_latitude": ref.latitude,
        "requested_longitude": ref.longitude,
        "returned_latitude": result.meta.returned_latitude,
        "returned_longitude": result.meta.returned_longitude,
        "coordinate_status": ref.coordinate_status,
        "metadata_source": ref.metadata_source,
        "district": ref.district,
        "timezone": result.meta.timezone,
        "http_status": result.meta.http_status,
        "hourly_row_count": len(records),
        "start_date": args.start,
        "end_date": args.end,
    }
    coords_path.write_text(json.dumps(coords_payload, indent=2, sort_keys=True), encoding="utf-8")

    summary = {
        **result.to_dict(),
        "coords_check": coords_payload,
        "raw_path": str(raw_path).replace("\\", "/"),
        "meta_path": str(meta_path).replace("\\", "/"),
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
