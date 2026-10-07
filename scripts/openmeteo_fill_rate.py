#!/usr/bin/env python3
"""Measure UCI weather fill potential from Open-Meteo processed Parquet (full range).

Example:
    python scripts/openmeteo_fill_rate.py --station Wanshouxigong
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from src.processing.openmeteo_to_processed import build_processed_key  # noqa: E402
from src.processing.uci_to_processed import build_processed_key as uci_key  # noqa: E402
from src.utils.minio_client import get_bucket, get_minio_client, get_object_bytes  # noqa: E402

PAIRS = (
    ("temperature_c", "om_temperature_c", "TEMP"),
    ("dew_point_c", "om_dew_point_c", "DEWP"),
    ("rain_mm", "om_rain_mm", "RAIN"),
    ("wind_speed_m_s", "om_wind_speed_m_s", "WSPM"),
    ("pressure_hpa", "om_surface_pressure_hpa", "PRES"),
)


def _read_parquet(key: str) -> pd.DataFrame:
    client = get_minio_client()
    bucket = get_bucket()
    return pd.read_parquet(io.BytesIO(get_object_bytes(client, bucket, key)))


def main() -> int:
    parser = argparse.ArgumentParser(description="OM fill-rate vs UCI processed")
    parser.add_argument("--station", default="Wanshouxigong")
    parser.add_argument("--uci-process-date", default="2026-10-07")
    parser.add_argument("--om-process-date", default="2026-10-07")
    parser.add_argument(
        "--out",
        default="artifacts/openmeteo/fill_rate_wanshouxigong.json",
    )
    args = parser.parse_args()

    u_key = uci_key(args.station, args.uci_process_date)
    o_key = build_processed_key(args.station, args.om_process_date)
    uci = _read_parquet(u_key)
    om = _read_parquet(o_key)
    uci["event_time_local"] = pd.to_datetime(uci["event_time_local"])
    om["event_time_local"] = pd.to_datetime(om["event_time_local"])
    merged = uci.merge(om, on="event_time_local", how="left", suffixes=("", "_om"))

    fill = {}
    for uci_col, om_col, label in PAIRS:
        missing = merged[uci_col].isna()
        n_miss = int(missing.sum())
        fillable = int((missing & merged[om_col].notna()).sum())
        fill[label] = {
            "uci_missing": n_miss,
            "uci_missing_pct": round(n_miss / len(merged) * 100, 4) if len(merged) else 0,
            "fillable_by_om": fillable,
            "fillable_of_missing_pct": round(fillable / n_miss * 100, 2) if n_miss else None,
        }

    cloud = {
        "null_pct": round(float(merged["om_cloud_cover_pct"].isna().mean() * 100), 4),
        "min": float(merged["om_cloud_cover_pct"].min()),
        "max": float(merged["om_cloud_cover_pct"].max()),
    }

    report = {
        "station": args.station,
        "uci_key": u_key,
        "om_key": o_key,
        "uci_rows": int(len(uci)),
        "om_rows": int(len(om)),
        "joined_rows": int(len(merged)),
        "om_matched_pct": round(merged["om_temperature_c"].notna().mean() * 100, 4),
        "fill_potential": fill,
        "cloud_cover": cloud,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
