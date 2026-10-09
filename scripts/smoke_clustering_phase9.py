#!/usr/bin/env python3
"""Phase 9a kickoff: smoke DWH window + episode mart for clustering.

Example:
    py -3 scripts/smoke_clustering_phase9.py
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

from src.clustering.smoke import smoke_clustering_window  # noqa: E402


def main() -> int:
    try:
        report = smoke_clustering_window()
    except Exception as exc:  # noqa: BLE001 — smoke gate: capture DB down, etc.
        report = {
            "ok": False,
            "phase": "P9a",
            "error": str(exc),
            "hint": "Start Postgres (docker compose up -d postgres) and re-run.",
        }
    out = ROOT / "artifacts" / "clustering" / "kickoff_smoke.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    (out.parent / "figures").mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(out), **report}, ensure_ascii=False))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
