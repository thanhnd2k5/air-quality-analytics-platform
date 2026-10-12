#!/usr/bin/env python3
"""Phase 10d: load predictions to staging, build mart via dbt, QC check.

Example:
    py -3 scripts/run_forecasting_phase10d.py
"""

from __future__ import annotations

import json
import subprocess
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

from src.forecasting.persist import load_predictions_to_staging  # noqa: E402
from src.utils.dbt_runner import run_dbt  # noqa: E402

OUT = ROOT / "artifacts" / "forecasting"


def _run_dbt(args: list[str]) -> int:
    """Docker dbt image (repo standard); falls back to local dbt."""
    return run_dbt(args)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        load_info = load_predictions_to_staging()
    except Exception as exc:  # noqa: BLE001
        report = {
            "ok": False,
            "phase": "P10d",
            "step": "staging_load",
            "error": str(exc),
        }
        path = OUT / "mart_prediction_checks.json"
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False))
        return 1

    print(json.dumps({"step": "staging_load", **load_info}, ensure_ascii=False))

    rc_run = _run_dbt(["run", "--select", "mart_pm25_predictions"])
    if rc_run != 0:
        report = {
            "ok": False,
            "phase": "P10d",
            "step": "dbt_run",
            "returncode": rc_run,
            "staging": load_info,
        }
        print(json.dumps(report, ensure_ascii=False))
        return 1

    rc_test = _run_dbt(["test", "--select", "mart_pm25_predictions"])
    if rc_test != 0:
        # still run check script for diagnostics
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "check_mart_predictions.py")],
            cwd=str(ROOT),
            check=False,
        )
        report = {
            "ok": False,
            "phase": "P10d",
            "step": "dbt_test",
            "returncode": rc_test,
            "staging": load_info,
        }
        print(json.dumps(report, ensure_ascii=False))
        return 1

    # Also run singular SQL grain test via select name if present
    _run_dbt(["test", "--select", "mart_pm25_predictions_grain_unique"])

    check = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_mart_predictions.py")],
        cwd=str(ROOT),
        check=False,
    )
    ok = check.returncode == 0
    print(
        json.dumps(
            {
                "ok": ok,
                "phase": "P10d",
                "staging": load_info,
                "dbt_run": rc_run,
                "dbt_test": rc_test,
                "check_returncode": check.returncode,
            },
            ensure_ascii=False,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
