"""Phase 9 kickoff smoke checks against DWH / mart."""

from __future__ import annotations

from typing import Any

from src.eda.db import fetch_dicts

# Profile window (exclude partial 2017 — P8 EDA note).
PROFILE_START = "2013-03-01 00:00:00"
PROFILE_END = "2016-12-31 23:00:00"
EXPECTED_STATIONS = 12


def smoke_clustering_window() -> dict[str, Any]:
    """Gate P9a: fact rows in profile window, 12 stations, episode mart reachable."""
    fact_sql = """
        select
            count(*)::bigint as row_count,
            count(distinct station_key)::int as station_count,
            min(event_time_local) as min_event_time,
            max(event_time_local) as max_event_time,
            count(pm25_ug_m3)::bigint as pm25_non_null
        from dwh.fact_air_quality_hourly
        where event_time_local >= %(start)s::timestamp
          and event_time_local <= %(end)s::timestamp
    """
    params = {"start": PROFILE_START, "end": PROFILE_END}
    fact_rows = fetch_dicts(fact_sql, params)
    fact = fact_rows[0] if fact_rows else {}

    episode_sql = """
        select count(*)::bigint as episode_row_count
        from mart.mart_pm25_episodes
    """
    ep_rows = fetch_dicts(episode_sql)
    episode_count = ep_rows[0].get("episode_row_count") if ep_rows else None

    station_count = fact.get("station_count") or 0
    row_count = fact.get("row_count") or 0
    ok = (
        station_count == EXPECTED_STATIONS
        and row_count > 0
        and episode_count is not None
        and int(episode_count) > 0
    )

    def _ser(v: Any) -> Any:
        return v.isoformat(sep=" ") if hasattr(v, "isoformat") else v

    return {
        "ok": ok,
        "phase": "P9a",
        "profile_window": {"start": PROFILE_START, "end": PROFILE_END},
        "expected_station_count": EXPECTED_STATIONS,
        "fact_in_window": {k: _ser(v) for k, v in fact.items()},
        "mart_pm25_episodes_row_count": int(episode_count) if episode_count is not None else None,
    }
