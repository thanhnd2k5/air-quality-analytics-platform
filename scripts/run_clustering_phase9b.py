#!/usr/bin/env python3
"""Phase 9b: build station pollution profiles CSV + QC report.

Example:
    py -3 scripts/run_clustering_phase9b.py
"""

from __future__ import annotations

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

from src.clustering.profiles import (  # noqa: E402
    fetch_station_profiles,
    qc_station_profiles,
)

OUT = ROOT / "artifacts" / "clustering"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "figures").mkdir(parents=True, exist_ok=True)

    try:
        df = fetch_station_profiles()
    except Exception as exc:  # noqa: BLE001
        report = {
            "ok": False,
            "phase": "P9b",
            "error": str(exc),
            "hint": "Start Postgres (docker compose up -d postgres) and re-run.",
        }
        path = OUT / "profile_qc.json"
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"output": str(path), **report}, ensure_ascii=False))
        return 1

    csv_path = OUT / "station_profiles.csv"
    df.to_csv(csv_path, index=False)

    qc = qc_station_profiles(df)
    qc_path = OUT / "profile_qc.json"
    payload = {
        "phase": "P9b",
        "csv": str(csv_path.relative_to(ROOT)).replace("\\", "/"),
        "sql": "sql/clustering/station_pollution_profile.sql",
        **qc,
    }
    qc_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "csv": str(csv_path),
                "qc": str(qc_path),
                "ok": qc["ok"],
                "row_count": qc["row_count"],
                "issues": qc["issues"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if qc["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
