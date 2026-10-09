#!/usr/bin/env python3
"""Compare mart.mart_pm25_predictions to Phase 10c lock / predictions artifact."""

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
from src.forecasting.persist import load_predictions_frame  # noqa: E402

LOCK = ROOT / "artifacts" / "forecasting" / "model_lock.json"


def main() -> int:
    issues: list[str] = []
    try:
        expected = load_predictions_frame()
    except Exception as exc:  # noqa: BLE001
        report = {"ok": False, "phase": "P10d", "error": str(exc)}
        out = ROOT / "artifacts" / "forecasting" / "mart_prediction_checks.json"
        out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"output": str(out), **report}, ensure_ascii=False))
        return 1

    rows = fetch_dicts(
        """
        select
            count(*)::bigint as row_count,
            count(distinct station_key)::int as station_count,
            count(distinct model_version)::int as model_version_count,
            avg(absolute_error)::float as mae_all,
            avg(absolute_error) filter (where split = 'test')::float as mae_test
        from mart.mart_pm25_predictions
        """
    )
    stats = rows[0] if rows else {}

    if int(stats.get("row_count") or 0) != len(expected):
        issues.append(
            f"row_count {stats.get('row_count')} != expected {len(expected)}"
        )
    if int(stats.get("station_count") or 0) != int(expected["station_key"].nunique()):
        issues.append("station_count mismatch")

    split_rows = fetch_dicts(
        """
        select split, count(*)::bigint as n
        from mart.mart_pm25_predictions
        group by split
        order by split
        """
    )
    mart_splits = {r["split"]: int(r["n"]) for r in split_rows}
    exp_splits = expected["split"].value_counts().to_dict()
    for k, v in exp_splits.items():
        if mart_splits.get(k) != int(v):
            issues.append(f"split {k}: mart={mart_splits.get(k)} expected={int(v)}")

    # Spot-check a few rows against artifact
    sample = expected.sample(n=min(5, len(expected)), random_state=42)
    for _, row in sample.iterrows():
        hit = fetch_dicts(
            """
            select predicted_pm25, actual_pm25, absolute_error
            from mart.mart_pm25_predictions
            where station_key = %(sk)s
              and prediction_origin_time = %(t)s
            """,
            {
                "sk": int(row["station_key"]),
                "t": row["prediction_origin_time"].to_pydatetime(),
            },
        )
        if not hit:
            issues.append(
                f"missing row station={row['station_key']} t={row['prediction_origin_time']}"
            )
            continue
        m = hit[0]
        if abs(float(m["predicted_pm25"]) - float(row["predicted_pm25"])) > 1e-6:
            issues.append("predicted_pm25 mismatch on spot-check")
        if abs(float(m["actual_pm25"]) - float(row["actual_pm25"])) > 1e-6:
            issues.append("actual_pm25 mismatch on spot-check")

    lock_test_mae = None
    if LOCK.is_file():
        lock = json.loads(LOCK.read_text(encoding="utf-8"))
        lock_test_mae = lock.get("test_mae", {}).get(lock.get("locked_model"))
        mart_test_mae = stats.get("mae_test")
        if lock_test_mae is not None and mart_test_mae is not None:
            if abs(float(mart_test_mae) - float(lock_test_mae)) > 0.05:
                issues.append(
                    f"test MAE mart={mart_test_mae:.4f} vs lock={lock_test_mae:.4f}"
                )

    ok = len(issues) == 0
    report = {
        "ok": ok,
        "phase": "P10d",
        "mart_row_count": int(stats.get("row_count") or 0),
        "expected_row_count": int(len(expected)),
        "station_count": int(stats.get("station_count") or 0),
        "split_counts": mart_splits,
        "mae_all": stats.get("mae_all"),
        "mae_test": stats.get("mae_test"),
        "lock_test_mae": lock_test_mae,
        "model_version_count": int(stats.get("model_version_count") or 0),
        "issues": issues,
    }
    out = ROOT / "artifacts" / "forecasting" / "mart_prediction_checks.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(out), **report}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
