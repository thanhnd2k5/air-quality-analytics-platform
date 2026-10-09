#!/usr/bin/env python3
"""Phase 10a kickoff: smoke DWH ML window + cluster mart for forecasting.

Example:
    py -3 scripts/smoke_forecasting_phase10.py
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

from src.forecasting.smoke import smoke_forecasting_prereqs  # noqa: E402


def main() -> int:
    try:
        report = smoke_forecasting_prereqs()
    except Exception as exc:  # noqa: BLE001 — smoke gate: capture DB down, etc.
        report = {
            "ok": False,
            "phase": "P10a",
            "error": str(exc),
            "hint": "Start Postgres (docker compose up -d postgres) and ensure dbt marts exist.",
        }
    out = ROOT / "artifacts" / "forecasting" / "kickoff_smoke.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    (out.parent / "figures").mkdir(parents=True, exist_ok=True)
    models_dir = ROOT / "models" / "pm25_forecast"
    models_dir.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(out), **report}, ensure_ascii=False))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
