#!/usr/bin/env python3
"""Compare dbt episode marts to Phase 8c Python lock artifacts."""

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

EXPECTED_STATION = 6318
EXPECTED_MULTI = 487


def main() -> int:
    station = fetch_dicts(
        """
        select
            count(*)::bigint as episode_count,
            count(distinct station_key)::int as station_count,
            min(duration_hours)::int as min_duration,
            round(percentile_cont(0.5) within group (order by duration_hours)::numeric, 2) as duration_median,
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
            round(percentile_cont(0.5) within group (order by duration_hours)::numeric, 2) as duration_median,
            min(multi_station_k)::int as multi_station_k,
            min(peak_station_count)::int as min_peak
        from mart.mart_pm25_multi_station_events
        """
    )[0]

    ok = (
        int(station["episode_count"]) == EXPECTED_STATION
        and int(multi["event_count"]) == EXPECTED_MULTI
        and int(station["min_duration"]) >= int(station["min_hours"])
        and int(multi["min_peak"]) >= int(multi["multi_station_k"])
        and float(station["threshold_ug_m3"]) == 115.0
        and int(station["min_hours"]) == 3
        and int(multi["multi_station_k"]) == 6
    )

    report = {
        "ok": ok,
        "expected_station_episodes": EXPECTED_STATION,
        "expected_multi_events": EXPECTED_MULTI,
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
