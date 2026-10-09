#!/usr/bin/env python3
"""Compare mart.mart_station_cluster to Phase 9c cluster_lock.json."""

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

from src.eda.db import fetch_dicts  # noqa: E402

LOCK = ROOT / "artifacts" / "clustering" / "cluster_lock.json"


def _load_expected() -> dict:
    if not LOCK.is_file():
        raise FileNotFoundError(
            f"Missing {LOCK}. Run: py -3 scripts/run_clustering_phase9.py"
        )
    payload = json.loads(LOCK.read_text(encoding="utf-8"))
    assignment = {
        int(row["station_key"]): int(row["cluster_id"])
        for row in payload["assignment"]
    }
    return {
        "method": payload["method"],
        "k": int(payload["k"]),
        "feature_set_version": payload["feature_set_version"],
        "n_stations": len(assignment),
        "assignment": assignment,
    }


def main() -> int:
    expected = _load_expected()

    rows = fetch_dicts(
        """
        select
            station_key,
            cluster_id,
            method,
            k,
            feature_set_version
        from mart.mart_station_cluster
        order by station_key
        """
    )

    issues: list[str] = []
    if len(rows) != expected["n_stations"]:
        issues.append(f"row_count {len(rows)} != {expected['n_stations']}")

    mart_map: dict[int, int] = {}
    for row in rows:
        sk = int(row["station_key"])
        cid = int(row["cluster_id"])
        mart_map[sk] = cid
        if row["method"] != expected["method"]:
            issues.append(f"station {sk}: method {row['method']!r}")
        if int(row["k"]) != expected["k"]:
            issues.append(f"station {sk}: k {row['k']}")
        if row["feature_set_version"] != expected["feature_set_version"]:
            issues.append(f"station {sk}: feature_set_version mismatch")
        if expected["assignment"].get(sk) != cid:
            issues.append(
                f"station {sk}: cluster_id {cid} != lock {expected['assignment'].get(sk)}"
            )

    missing = set(expected["assignment"]) - set(mart_map)
    extra = set(mart_map) - set(expected["assignment"])
    if missing:
        issues.append(f"missing station_keys: {sorted(missing)}")
    if extra:
        issues.append(f"extra station_keys: {sorted(extra)}")

    ok = len(issues) == 0
    report = {
        "ok": ok,
        "expected_from": str(LOCK.relative_to(ROOT)).replace("\\", "/"),
        "expected": {
            "method": expected["method"],
            "k": expected["k"],
            "feature_set_version": expected["feature_set_version"],
            "n_stations": expected["n_stations"],
        },
        "mart_row_count": len(rows),
        "issues": issues,
    }
    out = ROOT / "artifacts" / "clustering" / "mart_cluster_checks.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(out), **report}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
