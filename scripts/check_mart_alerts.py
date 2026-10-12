#!/usr/bin/env python3
"""Compare mart.mart_pm25_alerts to the classifier lock (artifacts/classification/model_lock.json).

The test confusion matrix rebuilt with GROUP BY outcome in the warehouse must equal the
one computed in Python, for both the locked model and the persistence baseline.
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

from src.classification.persist import load_alert_frame  # noqa: E402
from src.eda.db import fetch_dicts  # noqa: E402

LOCK = ROOT / "artifacts" / "classification" / "model_lock.json"
OUT = ROOT / "artifacts" / "classification" / "mart_alert_checks.json"


def _confusion(column: str) -> dict[str, int]:
    rows = fetch_dicts(
        f"""
        select {column} as outcome, count(*)::bigint as n
        from mart.mart_pm25_alerts
        where split = 'test'
        group by 1
        """
    )
    return {r["outcome"].lower(): int(r["n"]) for r in rows}


def main() -> int:
    issues: list[str] = []
    expected = load_alert_frame()
    lock = json.loads(LOCK.read_text(encoding="utf-8"))

    stats = fetch_dicts(
        """
        select count(*)::bigint as row_count,
               count(distinct station_key)::int as station_count,
               count(distinct model_version)::int as model_version_count
        from mart.mart_pm25_alerts
        """
    )[0]
    if int(stats["row_count"]) != len(expected):
        issues.append(f"row_count {stats['row_count']} != expected {len(expected)}")
    if int(stats["station_count"]) != int(expected["station_key"].nunique()):
        issues.append("station_count mismatch")

    mart_locked = _confusion("outcome")
    mart_persistence = _confusion("persistence_outcome")
    lock_locked = {k: lock["test"][lock["locked_model"]][k] for k in ("tp", "fp", "fn", "tn")}
    lock_persistence = {k: lock["test"]["persistence"][k] for k in ("tp", "fp", "fn", "tn")}
    for k in ("tp", "fp", "fn", "tn"):
        if mart_locked.get(k, 0) != lock_locked[k]:
            issues.append(f"locked {k}: mart={mart_locked.get(k, 0)} lock={lock_locked[k]}")
        if mart_persistence.get(k, 0) != lock_persistence[k]:
            issues.append(f"persistence {k}: mart={mart_persistence.get(k, 0)} lock={lock_persistence[k]}")

    onset = fetch_dicts(
        """
        select count(*) filter (where is_onset)::bigint as onsets,
               count(*) filter (where is_onset and predicted_alert = 1)::bigint as detected
        from mart.mart_pm25_alerts
        where split = 'test'
        """
    )[0]
    if int(onset["onsets"]) != lock["onset_recall_test"]["locked"]["onsets"]:
        issues.append("onset count mismatch")

    report = {
        "ok": not issues,
        "mart_row_count": int(stats["row_count"]),
        "expected_row_count": int(len(expected)),
        "station_count": int(stats["station_count"]),
        "model_version_count": int(stats["model_version_count"]),
        "test_confusion_mart": {"locked": mart_locked, "persistence": mart_persistence},
        "test_confusion_lock": {"locked": lock_locked, "persistence": lock_persistence},
        "test_onsets": {k: int(v) for k, v in onset.items()},
        "issues": issues,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), **report}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
