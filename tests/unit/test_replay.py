"""A replay hides the next hour until the watermark reaches it."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.classification.replay import assert_feature_names, replay_alerts, view_at


def _origins() -> pd.DataFrame:
    times = pd.date_range("2016-12-20 00:00:00", periods=3, freq="h")
    return pd.DataFrame(
        {
            "station_key": 1,
            "station_name": "Gucheng",
            "event_time_local": times,
            "pm25_ug_m3": [80.0, 90.0, 120.0],
            "pm10_ug_m3": [100.0, 110.0, 140.0],
            "co_ug_m3": [900.0, 1000.0, 1100.0],
            "pm25_lag_1": [70.0, 80.0, 90.0],
            "y_true_hidden": [90.0, 120.0, 130.0],
            "suspect_spatiotemporal": [True, True, True],
        }
    )


def test_watermark_hides_the_target_and_the_review_flag():
    seen: list[pd.DataFrame] = []

    def predict(features: pd.DataFrame) -> np.ndarray:
        seen.append(features.copy())
        return np.full(len(features), 0.8)

    suspect = pd.DataFrame(
        {
            "station_key": [1, 1],
            "event_time_local": pd.to_datetime(["2016-12-20 01:00:00", "2016-12-20 02:00:00"]),
            "suspect_spatiotemporal": [True, False],
        }
    )
    result = replay_alerts(
        _origins(),
        predict,
        start="2016-12-20 00:00:00",
        end="2016-12-20 02:00:00",
        batch_hours=1,
        model_version="histgb-alert-0.50",
        cutoff=0.5,
        feature_cols=["pm25_lag_1"],
        suspect=suspect,
    )
    assert all("y_true_hidden" not in frame.columns for frame in seen)
    assert all("suspect_spatiotemporal" not in frame.columns for frame in seen)

    at_origin = view_at(result["rows"], "2016-12-20 00:00:00")
    assert len(at_origin) == 1
    assert at_origin[0]["status"] == "waiting"
    assert at_origin[0]["y_true"] is None
    assert at_origin[0]["suspect_spatiotemporal"] is None

    at_target = view_at(result["rows"], "2016-12-20 01:00:00")
    first = next(row for row in at_target if row["origin_time"].endswith("00:00:00"))
    assert first["status"] == "scored"
    assert first["y_true"] == 90.0
    assert first["suspect_spatiotemporal"] is True
    second = next(row for row in at_target if row["origin_time"].endswith("01:00:00"))
    assert second["status"] == "waiting"
    assert second["suspect_spatiotemporal"] is None


def test_feature_names_reject_the_review_flag():
    with pytest.raises(RuntimeError):
        assert_feature_names(["pm25_ug_m3", "suspect_spatiotemporal"])
