"""Unit tests for Phase 8 episode island logic (no database required)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.eda.episodes import (
    _island_ids,
    choose_locked_rule,
    detect_multi_station_events,
    detect_station_episodes,
    hourly_station_counts,
    mark_in_episode,
)


def _station_frame(
    pm25: list[float | None],
    *,
    station_key: int = 1,
    station_name: str = "TestStation",
    start: str = "2015-01-01 00:00:00",
) -> pd.DataFrame:
    times = pd.date_range(start, periods=len(pm25), freq="h")
    return pd.DataFrame(
        {
            "station_key": station_key,
            "station_name": station_name,
            "event_time_local": times,
            "pm25_ug_m3": pm25,
            "temperature_c": [10.0] * len(pm25),
            "relative_humidity_pct": [50.0] * len(pm25),
            "wind_speed_m_s": [2.0] * len(pm25),
            "rain_mm": [0.0] * len(pm25),
            "cloud_cover_pct": [40.0] * len(pm25),
            "year": [t.year for t in times],
            "season": ["winter"] * len(pm25),
        }
    )


def test_island_ids_basic_runs():
    dirty = np.array([False, True, True, False, True, False, True, True, True])
    assert _island_ids(dirty).tolist() == [0, 1, 1, 0, 2, 0, 3, 3, 3]


def test_island_ids_empty_and_all_clean():
    assert _island_ids(np.array([], dtype=bool)).tolist() == []
    assert _island_ids(np.array([False, False])).tolist() == [0, 0]


def test_null_and_below_threshold_break_runs():
    # threshold 115; null and 100 break; min_hours=2 keeps two short episodes
    df = _station_frame([120, 130, None, 140, 150, 100, 160, 170])
    episodes = detect_station_episodes(df, threshold=115.0, min_hours=2)
    assert len(episodes) == 3
    assert episodes["duration_hours"].tolist() == [2, 2, 2]


def test_min_hours_filters_one_hour_spike():
    df = _station_frame([50, 200, 50, 200, 210, 220, 50])
    episodes = detect_station_episodes(df, threshold=115.0, min_hours=3)
    assert len(episodes) == 1
    assert int(episodes.iloc[0]["duration_hours"]) == 3
    assert float(episodes.iloc[0]["pm25_max"]) == 220.0


def test_duration_hours_matches_inclusive_hour_span():
    df = _station_frame([200, 210, 220, 230, 50])
    episodes = detect_station_episodes(df, threshold=115.0, min_hours=3)
    assert len(episodes) == 1
    row = episodes.iloc[0]
    span = int((row["end_time"] - row["start_time"]) / pd.Timedelta(hours=1)) + 1
    assert int(row["duration_hours"]) == span == 4


def test_year_season_taken_from_episode_start():
    # Cross year-end: first hour Dec 31 → year/season from start, not Jan 1
    times = pd.date_range("2015-12-31 22:00:00", periods=4, freq="h")
    df = pd.DataFrame(
        {
            "station_key": 1,
            "station_name": "Boundary",
            "event_time_local": times,
            "pm25_ug_m3": [200.0, 200.0, 200.0, 50.0],
            "temperature_c": [0.0] * 4,
            "relative_humidity_pct": [50.0] * 4,
            "wind_speed_m_s": [1.0] * 4,
            "rain_mm": [0.0] * 4,
            "cloud_cover_pct": [40.0] * 4,
            "year": [t.year for t in times],
            "season": ["winter", "winter", "winter", "winter"],
        }
    )
    episodes = detect_station_episodes(df, threshold=115.0, min_hours=3)
    assert len(episodes) == 1
    assert int(episodes.iloc[0]["year"]) == 2015
    assert episodes.iloc[0]["start_time"] == times[0]


def test_mark_in_episode_only_qualifying_islands():
    df = _station_frame([200, 50, 200, 210, 220])
    marked = mark_in_episode(df, threshold=115.0, min_hours=3)
    assert marked.tolist() == [False, False, True, True, True]


def test_multi_station_event_requires_k_and_qualifying_episodes():
    # Station 1: 3h episode; station 2: 3h overlapping; station 3: only 1h spike
    s1 = _station_frame([200, 200, 200, 50], station_key=1, station_name="A")
    s2 = _station_frame([200, 200, 200, 50], station_key=2, station_name="B")
    s3 = _station_frame([200, 50, 50, 50], station_key=3, station_name="C")
    df = pd.concat([s1, s2, s3], ignore_index=True)

    counts = hourly_station_counts(df, threshold=115.0, min_hours=3)
    # hours 0-2: stations A+B in episode (C's single dirty hour dropped) → n=2
    assert counts["n_stations_in_episode"].tolist() == [2, 2, 2, 0]

    events_k2 = detect_multi_station_events(counts, k=2)
    assert len(events_k2) == 1
    assert int(events_k2.iloc[0]["duration_hours"]) == 3
    assert int(events_k2.iloc[0]["peak_station_count"]) == 2

    events_k3 = detect_multi_station_events(counts, k=3)
    assert events_k3.empty


def test_choose_locked_rule_coherent_network_uses_k6():
    # n>=3 common and n=12 >= 5% → K=6
    dist = pd.DataFrame(
        {
            "n_stations": [0, 3, 6, 12],
            "hour_count": [50, 20, 15, 15],  # total 100; ge3=50%, ge12=15%
        }
    )
    rule = choose_locked_rule(dist)
    assert rule.threshold_ug_m3 == 115.0
    assert rule.min_hours == 3
    assert rule.multi_station_k == 6


def test_choose_locked_rule_rare_concurrency_picks_smallest_k():
    dist = pd.DataFrame(
        {
            "n_stations": [0, 1, 3, 6],
            "hour_count": [90, 5, 4, 1],  # ge3=5% ≤ 15 → K=3
        }
    )
    rule = choose_locked_rule(dist)
    assert rule.multi_station_k == 3
