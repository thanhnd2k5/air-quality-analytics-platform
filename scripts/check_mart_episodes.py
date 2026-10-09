#!/usr/bin/env python3
"""Compare dbt episode marts to Phase 8c lock + Python CSV artifacts.

Parity layers:
1. episode_lock_summary.json (Python 8c run) vs mart row counts / params
2. episodes_*_locked.csv (same Python run) vs mart row counts
3. duration_hours vs inclusive hour span on mart rows
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

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
CSV_STATION = ROOT / "artifacts" / "eda" / "episodes_station_locked.csv"
CSV_MULTI = ROOT / "artifacts" / "eda" / "episodes_multi_station_locked.csv"


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


def _csv_counts() -> dict[str, int | None]:
    station_n = (
        int(len(pd.read_csv(CSV_STATION))) if CSV_STATION.is_file() else None
    )
    multi_n = int(len(pd.read_csv(CSV_MULTI))) if CSV_MULTI.is_file() else None
    return {
        "episodes_station_locked_csv": station_n,
        "episodes_multi_station_locked_csv": multi_n,
    }


def main() -> int:
    expected = _load_expected()
    csv_counts = _csv_counts()
    issues: list[str] = []

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

    duration_mismatches = fetch_dicts(
        """
        select
            (
                select count(*)::bigint
                from mart.mart_pm25_episodes
                where duration_hours
                    <> (extract(epoch from (end_time - start_time)) / 3600)::integer + 1
            ) as station_duration_mismatches,
            (
                select count(*)::bigint
                from mart.mart_pm25_multi_station_events
                where duration_hours
                    <> (extract(epoch from (end_time - start_time)) / 3600)::integer + 1
            ) as multi_duration_mismatches
        """
    )[0]

    mart_station_n = int(station["episode_count"])
    mart_multi_n = int(multi["event_count"])

    if mart_station_n != expected["station_episodes"]:
        issues.append(
            f"mart station episodes {mart_station_n} != lock {expected['station_episodes']}"
        )
    if mart_multi_n != expected["multi_events"]:
        issues.append(
            f"mart multi events {mart_multi_n} != lock {expected['multi_events']}"
        )
    if int(station["min_duration"]) < int(station["min_hours"]):
        issues.append("station min_duration < min_hours")
    if int(multi["min_peak"]) < int(multi["multi_station_k"]):
        issues.append("multi min_peak < multi_station_k")
    if float(station["threshold_ug_m3"]) != expected["threshold_ug_m3"]:
        issues.append("threshold_ug_m3 mismatch vs lock")
    if int(station["min_hours"]) != expected["min_hours"]:
        issues.append("min_hours mismatch vs lock")
    if int(multi["multi_station_k"]) != expected["multi_station_k"]:
        issues.append("multi_station_k mismatch vs lock")

    csv_station = csv_counts["episodes_station_locked_csv"]
    csv_multi = csv_counts["episodes_multi_station_locked_csv"]
    if csv_station is None:
        issues.append(f"missing {CSV_STATION.name} (run run_eda_phase8c.py)")
    elif csv_station != mart_station_n:
        issues.append(
            f"CSV station episodes {csv_station} != mart {mart_station_n}"
        )
    elif csv_station != expected["station_episodes"]:
        issues.append(
            f"CSV station episodes {csv_station} != lock {expected['station_episodes']}"
        )

    if csv_multi is None:
        issues.append(f"missing {CSV_MULTI.name} (run run_eda_phase8c.py)")
    elif csv_multi != mart_multi_n:
        issues.append(f"CSV multi events {csv_multi} != mart {mart_multi_n}")
    elif csv_multi != expected["multi_events"]:
        issues.append(
            f"CSV multi events {csv_multi} != lock {expected['multi_events']}"
        )

    station_span_bad = int(duration_mismatches["station_duration_mismatches"])
    multi_span_bad = int(duration_mismatches["multi_duration_mismatches"])
    if station_span_bad:
        issues.append(f"station duration span mismatches: {station_span_bad}")
    if multi_span_bad:
        issues.append(f"multi duration span mismatches: {multi_span_bad}")

    ok = len(issues) == 0
    report = {
        "ok": ok,
        "issues": issues,
        "expected_from": str(LOCK_SUMMARY.relative_to(ROOT)).replace("\\", "/"),
        "expected": expected,
        "python_csv_counts": csv_counts,
        "mart_pm25_episodes": {
            k: (float(v) if hasattr(v, "as_tuple") else v) for k, v in station.items()
        },
        "mart_pm25_multi_station_events": {
            k: (float(v) if hasattr(v, "as_tuple") else v) for k, v in multi.items()
        },
        "duration_span_check": {
            "station_mismatches": station_span_bad,
            "multi_mismatches": multi_span_bad,
        },
    }
    out = ROOT / "artifacts" / "eda" / "mart_episode_checks.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(out), **report}, default=str))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
