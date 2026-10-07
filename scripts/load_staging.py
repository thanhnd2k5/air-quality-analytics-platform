#!/usr/bin/env python3
"""Load processed Parquet + station reference into PostgreSQL staging.

Examples:
    python scripts/load_staging.py --station Wanshouxigong
    python scripts/load_staging.py --all
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
from src.staging.load import load_stations  # noqa: E402
from src.staging.schema import DATASET_AIR, DATASET_OM  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Load processed lake data into PostgreSQL staging")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--station", help="Station name, e.g. Wanshouxigong")
    group.add_argument("--all", action="store_true", help="Load all stations in stations.csv")
    parser.add_argument(
        "--skip-reference",
        action="store_true",
        help="Do not reload staging.station_reference",
    )
    parser.add_argument(
        "--dataset",
        choices=(DATASET_AIR, DATASET_OM),
        action="append",
        help="Limit hourly datasets (repeatable). Default: both.",
    )
    args = parser.parse_args()

    stations = list_station_names() if args.all else [args.station]
    datasets = tuple(args.dataset) if args.dataset else (DATASET_AIR, DATASET_OM)
    results = load_stations(
        stations,
        include_reference=not args.skip_reference,
        datasets=datasets,
    )
    exit_code = 0
    for result in results:
        print(json.dumps(result.to_dict(), ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
