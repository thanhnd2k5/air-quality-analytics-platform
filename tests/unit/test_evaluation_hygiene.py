"""Label windows stay inside a split, and profile windows ignore later hours."""

from __future__ import annotations

import pandas as pd

from src.classification.label_window import (
    DEVELOPMENT_FOLDS,
    TimeFold,
    assign_time_fold,
    rows_inside_split,
)
from src.clustering.window_profiles import assignment_agreement, episode_runs, station_profiles


def test_point_label_stops_at_the_split_end():
    times = pd.to_datetime(
        [
            "2015-12-31 21:00:00",
            "2015-12-31 22:00:00",
            "2015-12-31 23:00:00",
            "2016-01-01 00:00:00",
        ]
    )
    split = pd.Series(["train", "train", "train", "val"])
    ends = {"train": "2015-12-31 23:00:00", "val": "2016-06-30 23:00:00"}
    inside = rows_inside_split(times, split, ends, label_hours=1)
    assert inside.tolist() == [True, True, False, True]


def test_onset_confirmation_needs_eight_hours_and_stations_share_the_clock():
    times = pd.to_datetime(["2015-12-31 15:00:00", "2015-12-31 16:00:00"] * 2)
    split = pd.Series(["train", "train", "train", "train"])
    ends = {"train": "2015-12-31 23:00:00"}
    inside = rows_inside_split(times, split, ends, label_hours=8)
    assert inside.tolist() == [True, False, True, False]


def test_stored_deadline_is_what_the_row_uses():
    times = pd.to_datetime(["2015-12-31 22:00:00"])
    deadline = pd.to_datetime(["2016-01-01 00:00:00"])
    inside = rows_inside_split(
        times,
        pd.Series(["train"]),
        {"train": "2015-12-31 23:00:00"},
        label_hours=1,
        deadline=deadline,
    )
    assert not bool(inside.iloc[0])


def test_fold_leaves_a_gap_unlabeled_and_stops_before_the_held_out_half():
    fold = TimeFold("gap", "2015-06-30 22:00:00", "2015-07-01 00:00:00", "2015-12-31 23:00:00")
    times = pd.to_datetime(
        [
            "2015-06-30 22:00:00",
            "2015-06-30 23:00:00",
            "2015-07-01 00:00:00",
            "2016-07-01 00:00:00",
        ]
    )
    labels = assign_time_fold(times, fold)
    assert labels.iloc[0] == "train"
    assert pd.isna(labels.iloc[1])
    assert labels.iloc[2] == "val"
    assert pd.isna(labels.iloc[3])
    assert DEVELOPMENT_FOLDS[-1].val_end == "2016-06-30 23:00:00"


def _hours(specs: list[tuple[str, float]]) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "station_key": 1,
            "station_name": "Dongsi",
            "district": "Dongcheng",
            "event_time_local": pd.to_datetime([item[0] for item in specs]),
            "pm25_ug_m3": [item[1] for item in specs],
        }
    )
    for column in ("pm10_ug_m3", "no2_ug_m3", "co_ug_m3", "so2_ug_m3", "o3_ug_m3"):
        frame[column] = frame["pm25_ug_m3"]
    return frame


def test_profile_mean_and_episode_do_not_read_past_the_cutoff():
    frame = _hours(
        [
            ("2015-12-31 21:00:00", 5),
            ("2015-12-31 22:00:00", 200),
            ("2015-12-31 23:00:00", 200),
            ("2016-01-01 00:00:00", 200),
            ("2016-01-01 01:00:00", 200),
            ("2016-01-01 02:00:00", 200),
            ("2016-01-01 03:00:00", 200),
            ("2016-01-01 04:00:00", 1000),
        ]
    )
    inside = station_profiles(
        frame,
        window_start="2015-12-31 21:00:00",
        window_end="2015-12-31 23:00:00",
        episode_mode="inside",
    )
    continued = station_profiles(
        frame,
        window_start="2015-12-31 21:00:00",
        window_end="2015-12-31 23:00:00",
        episode_mode="start_in_window",
    )
    assert float(inside.loc[0, "mean_pm25"]) == 135.0
    assert int(inside.loc[0, "episode_count"]) == 0
    assert int(continued.loc[0, "episode_count"]) == 1
    assert int(continued.loc[0, "total_episode_hours"]) == 7
    runs = episode_runs(frame)
    assert int(runs.loc[0, "duration_hours"]) == 7


def test_agreement_ignores_a_label_swap_and_names_a_move():
    left = pd.DataFrame(
        {
            "station_key": [1, 2, 3, 4],
            "station_name": ["A", "B", "C", "D"],
            "cluster_id": [0, 0, 0, 1],
        }
    )
    swapped = left.assign(cluster_id=[1, 1, 1, 0])
    moved = left.assign(cluster_id=[0, 1, 0, 1])
    same = assignment_agreement(left, swapped)
    changed = assignment_agreement(left, moved)
    assert same["pairwise_agreement"] == 1.0
    assert same["n_moved"] == 0
    assert changed["n_moved"] == 1
    assert changed["moved_stations"] == ["B"]
