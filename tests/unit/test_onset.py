"""Episode-onset labels use t+1..t+8 and the false-alarm budget is applied before recall."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.classification.onset import (
    FOLDS_REQUIRED,
    choose_operating_point,
    clears_recall_margin,
    episode_metrics,
    fold_support,
    mark_onset_origins,
    trend_score,
)


def _hourly(values, start="2015-01-01 00:00:00", station=1) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "station_key": station,
            "event_time_local": pd.date_range(start, periods=len(values), freq="h"),
            "pm25_ug_m3": values,
        }
    )


def _origin(hourly, at, pm25) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "station_key": [1],
            "event_time_local": [pd.Timestamp(at)],
            "pm25_ug_m3": [pm25],
        }
    )


def test_episode_starting_next_hour_is_positive_and_a_later_start_can_fall_outside():
    hourly = _hourly([10, 200, 200, 200, 10, 10, 10, 10, 10])
    marked = mark_onset_origins(_origin(hourly, "2015-01-01 00:00:00", 10), hourly)
    assert int(marked.loc[0, "y_onset"]) == 1
    assert marked.loc[0, "lead_hours"] == 1
    assert int(marked.loc[0, "episode_duration_h"]) == 3
    assert marked.loc[0, "episode_peak"] == 200

    later = _hourly([10, 10, 10, 10, 10, 10, 10, 200, 200, 200])
    marked_later = mark_onset_origins(_origin(later, "2015-01-01 00:00:00", 10), later)
    assert int(marked_later.loc[0, "y_onset"]) == 0
    assert pd.isna(marked_later.loc[0, "episode_start"])


def test_start_at_the_sixth_hour_is_positive_and_a_short_run_is_not():
    values = [10] * 9
    values[6] = values[7] = values[8] = 200
    marked = mark_onset_origins(_origin(None, "2015-01-01 00:00:00", 10), _hourly(values))
    assert int(marked.loc[0, "y_onset"]) == 1
    assert marked.loc[0, "lead_hours"] == 6

    short = [10] * 9
    short[1] = short[2] = 200
    marked_short = mark_onset_origins(_origin(None, "2015-01-01 00:00:00", 10), _hourly(short))
    assert int(marked_short.loc[0, "y_onset"]) == 0


def test_missing_confirmation_hour_null_break_and_dirty_now_are_ineligible_or_negative():
    short_clock = _hourly([10, 200, 200, 200, 10, 10, 10, 10])
    marked = mark_onset_origins(_origin(None, "2015-01-01 00:00:00", 10), short_clock)
    assert pd.isna(marked.loc[0, "y_onset"])
    assert not bool(marked.loc[0, "onset_clock_ok"])

    broken = [10, 200, 200, np.nan, 200, 10, 10, 10, 10]
    marked_broken = mark_onset_origins(_origin(None, "2015-01-01 00:00:00", 10), _hourly(broken))
    assert int(marked_broken.loc[0, "y_onset"]) == 0

    dirty_now = mark_onset_origins(
        _origin(None, "2015-01-01 00:00:00", 115),
        _hourly([115, 200, 200, 200, 10, 10, 10, 10, 10]),
    )
    assert pd.isna(dirty_now.loc[0, "y_onset"])
    assert not bool(dirty_now.loc[0, "onset_clean_now"])


def test_false_alarm_budget_keeps_the_cut_with_higher_episode_recall():
    frame = pd.DataFrame(
        {
            "station_key": [1, 1, 1, 1],
            "event_time_local": pd.to_datetime(
                [
                    "2015-01-01 00:00:00",
                    "2015-01-01 01:00:00",
                    "2015-01-02 00:00:00",
                    "2015-01-03 00:00:00",
                ]
            ),
            "y_onset": [0, 1, 0, 1],
            "episode_start": [pd.NaT, "2015-01-01 02:00:00", pd.NaT, "2015-01-03 04:00:00"],
            "lead_hours": [np.nan, 1, np.nan, 4],
        }
    )
    chosen = choose_operating_point([0.2, 0.9, 0.8, 0.6], frame, [0.95, 0.85, 0.50, 0.10], 0.5)
    assert chosen["budget_met"]
    assert chosen["threshold"] == 0.5
    assert chosen["metrics"]["episode_recall"] == 1
    assert chosen["metrics"]["n_detected"] == 2
    assert chosen["metrics"]["fp_origins"] == 1
    assert not clears_recall_margin(0.54, 0.50)
    assert clears_recall_margin(0.55, 0.50)
    assert fold_support([True, True, False], FOLDS_REQUIRED)
    assert not fold_support([True, False, False], FOLDS_REQUIRED)


def test_one_alert_detects_the_episode_and_trend_score_ignores_a_fall():
    frame = pd.DataFrame(
        {
            "station_key": [1, 1],
            "event_time_local": pd.to_datetime(["2015-01-01 00:00:00", "2015-01-01 02:00:00"]),
            "y_onset": [1, 1],
            "episode_start": ["2015-01-01 04:00:00", "2015-01-01 04:00:00"],
            "lead_hours": [4, 2],
        }
    )
    metrics = episode_metrics(frame, [0, 1])
    assert metrics["n_episodes"] == 1
    assert metrics["n_detected"] == 1
    assert metrics["median_lead_h"] == 2
    assert metrics["median_alerts_per_detected"] == 1
    assert np.allclose(trend_score([40, 40], [5, -10]), [70, 40])
