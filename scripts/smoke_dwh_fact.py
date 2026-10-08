#!/usr/bin/env python3
"""Phase 8 kickoff: smoke-check dwh.fact_air_quality_hourly is ready for EDA.

Example:
    python scripts/smoke_dwh_fact.py
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

from src.eda.db import smoke_fact_air_quality  # noqa: E402


def main() -> int:
    report = smoke_fact_air_quality()
    out = ROOT / "artifacts" / "eda" / "smoke_fact.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(out), **report}, ensure_ascii=False))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
