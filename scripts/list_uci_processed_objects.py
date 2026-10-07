"""List MinIO processed/uci/air_quality objects (Phase 4 evidence)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.utils.minio_client import get_bucket, get_minio_client, list_object_names  # noqa: E402


def main() -> int:
    client = get_minio_client()
    bucket = get_bucket()
    names = list_object_names(client, bucket, prefix="processed/uci/air_quality/")
    stations = sorted(
        {n.split("station=")[1].split("/")[0] for n in names if "station=" in n}
    )
    parquets = [n for n in names if n.endswith(".parquet")]
    out = {
        "bucket": bucket,
        "object_count": len(names),
        "parquet_count": len(parquets),
        "stations": stations,
        "station_count": len(stations),
        "objects": names,
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
