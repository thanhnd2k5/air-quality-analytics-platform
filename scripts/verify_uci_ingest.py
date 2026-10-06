"""Verify MinIO raw object matches local UCI source (P3-11)."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ingestion.uci_to_minio import sha256_file  # noqa: E402
from src.utils.minio_client import (  # noqa: E402
    get_bucket,
    get_minio_client,
    get_object_bytes,
    get_object_metadata,
)


def main() -> int:
    key = (
        "raw/uci/air_quality/station=Wanshouxigong/ingestion_date=2026-10-06/"
        "PRSA_Data_Wanshouxigong_20130301-20170228.csv"
    )
    local = ROOT / "data/raw/uci/PRSA_Data_Wanshouxigong_20130301-20170228.csv"
    local_sha, local_size = sha256_file(local)

    client = get_minio_client()
    bucket = get_bucket()
    remote = get_object_bytes(client, bucket, key)
    remote_sha = hashlib.sha256(remote).hexdigest()
    user_meta = get_object_metadata(client, bucket, key)
    sidecar = json.loads(get_object_bytes(client, bucket, f"{key}.meta.json"))

    out = {
        "object_key": key,
        "local_sha256": local_sha,
        "remote_sha256": remote_sha,
        "sidecar_sha256": sidecar.get("sha256"),
        "user_meta_sha256": user_meta.get("sha256"),
        "byte_identical": local_sha == remote_sha,
        "sizes": {"local": local_size, "remote": len(remote)},
        "sidecar_station": sidecar.get("station"),
        "ok": local_sha == remote_sha == sidecar.get("sha256")
        and sidecar.get("station") == "Wanshouxigong",
    }
    print(json.dumps(out, indent=2))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
