#!/usr/bin/env python3
"""Compare dbt episode marts to Phase 8c lock summary (not hard-coded counts)."""

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

LOCK_SUMMARY = ROOT / "artifacts" / "eda" / "episode_lock_summary.json"


def _load_expected() -> dict:
    if not LOCK_SUMMARY.is_file():
        raise FileNotFoundError(
            f"Missing {LOCK_SUMMARY}. Run: py -3 scripts/run_eda_phase8c.py"
        )
    payload = json.loads(LOCK_SUMMARY.read_text(encoding="utf-8"))
    rule = payload["locked_rule"]
    station_summary = payload["locked_station_episode_summary"]
    return {
        "threshold_ug_m3": float(rule["threshold_ug_m3"]),
        "min_hours": int(rule["min_hours"]),
        "multi_station_k": int(rule["multi_station_k"]),
        "station_episodes": int(station_summary["episode_count"]),
        "multi_events": int(payload["locked_multi_station_event_count"]),
    }


def main() -> int:
    expected = _load_expected()

    station = fetch_dicts(
        """
        select
            count(*)::bigint as episode_count,
            count(distinct station_key)::int as station_count,
            min(duration_hours)::int as min_duration,
            round(percentile_cont(0.5) within group (order by duration_hours)::numeric, 2)
                as duration_median,
            min(threshold_ug_m3)::float as threshold_ug_m3,
            min(min_hours)::int as min_hours
        from mart.mart_pm25_episodes
        """
    )[0]
    multi = fetch_dicts(
        """
        select
            count(*)::bigint as event_count,
            min(duration_hours)::int as min_duration,
            round(percentile_cont(0.5) within group (order by duration_hours)::numeric, 2)
                as duration_median,
            min(multi_station_k)::int as multi_station_k,
            min(peak_station_count)::int as min_peak
        from mart.mart_pm25_multi_station_events
        """
    )[0]

    ok = (
        int(station["episode_count"]) == expected["station_episodes"]
        and int(multi["event_count"]) == expected["multi_events"]
        and int(station["min_duration"]) >= int(station["min_hours"])
        and int(multi["min_peak"]) >= int(multi["multi_station_k"])
        and float(station["threshold_ug_m3"]) == expected["threshold_ug_m3"]
        and int(station["min_hours"]) == expected["min_hours"]
        and int(multi["multi_station_k"]) == expected["multi_station_k"]
    )

    report = {
        "ok": ok,
        "expected_from": str(LOCK_SUMMARY.relative_to(ROOT)).replace("\\", "/"),
        "expected": expected,
        "mart_pm25_episodes": {
            k: (float(v) if hasattr(v, "as_tuple") else v) for k, v in station.items()
        },
        "mart_pm25_multi_station_events": {
            k: (float(v) if hasattr(v, "as_tuple") else v) for k, v in multi.items()
        },
    }
    out = ROOT / "artifacts" / "eda" / "mart_episode_checks.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(out), **report}, default=str))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
