"""Spatial quality flags keep the original PM2.5 and do not know a calendar date."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.forecasting.spatial_calendar import add_spatial_features
from src.forecasting.spatial_quality import (
    aggregate_neighbors,
    attach_suspect_neighbor_influence,
    score_spatial_quality,
)

MODULE_PATH = Path(__file__).resolve().parents[2] / "src" / "forecasting" / "spatial_quality.py"


def _stations() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "station_name": ["A", "B", "C", "D"],
            "latitude": [40.00, 40.01, 40.02, 40.03],
            "longitude": [116.0, 116.0, 116.0, 116.0],
        }
    )


def _panel(rows: dict[str, list[float]], start: str = "2014-02-01 00:00:00") -> pd.DataFrame:
    times = pd.date_range(start, periods=3, freq="h")
    frame_rows = []
    for name, values in rows.items():
        for time, value in zip(times, values):
            frame_rows.append(
                {
                    "station_key": {"A": 1, "B": 2, "C": 3, "D": 4}[name],
                    "station_name": name,
                    "event_time_local": time,
                    "pm25_ug_m3": value,
                    "pm10_ug_m3": 80.0 if value < 10 else value,
                    "co_ug_m3": 3000.0 if value < 10 else 400.0,
                    "no2_ug_m3": 40.0,
                }
            )
    return pd.DataFrame(frame_rows)


def test_rule_module_has_no_diagnostic_date_or_replacement_values():
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "2016-12-20" not in text
    assert "170" not in text
    assert "398" not in text


def test_isolated_low_keeps_original_value_and_sets_flag():
    panel = _panel(
        {
            "A": [200, 3, 180],
            "B": [190, 180, 170],
            "C": [200, 190, 180],
            "D": [210, 200, 190],
        }
    )
    scored = score_spatial_quality(panel, _stations())
    origin = pd.Timestamp("2014-02-01 01:00:00")
    row = scored[(scored["station_name"] == "A") & (scored["event_time_local"] == origin)].iloc[0]
    assert row["pm25_ug_m3"] == 3
    assert row["suspect_spatiotemporal"]
    assert row["suspect_spatiotemporal_causal"]
    assert row["pm10_context"] == "pm10_disagrees"
    assert row["co_elevated"]
    assert row["neighbor_median"] > 100


def test_matching_low_neighborhood_is_not_flagged():
    panel = _panel({name: [3, 3, 3] for name in ("A", "B", "C", "D")})
    scored = score_spatial_quality(panel, _stations())
    assert not scored["suspect_spatiotemporal"].any()
    assert (scored["pm25_ug_m3"] == 3).all()


def test_persistent_local_low_is_not_an_isolated_spike():
    panel = _panel(
        {
            "A": [3, 3, 3],
            "B": [200, 200, 200],
            "C": [200, 200, 200],
            "D": [200, 200, 200],
        }
    )
    scored = score_spatial_quality(panel, _stations())
    row = scored[scored["station_name"] == "A"]
    assert not row["suspect_spatiotemporal"].any()
    assert (row["pm25_ug_m3"] == 3).all()


def test_offline_flag_needs_the_rebound_causal_flag_does_not():
    panel = _panel(
        {
            "A": [200, 3, 4],
            "B": [190, 180, 170],
            "C": [200, 190, 180],
            "D": [210, 200, 190],
        }
    )
    scored = score_spatial_quality(panel, _stations())
    origin = pd.Timestamp("2014-02-01 01:00:00")
    row = scored[(scored["station_name"] == "A") & (scored["event_time_local"] == origin)].iloc[0]
    assert row["pm25_ug_m3"] == 3
    assert not row["suspect_spatiotemporal"]
    assert row["suspect_spatiotemporal_causal"]


def test_same_values_on_another_date_get_the_same_flag():
    rows = {
        "A": [200, 3, 180],
        "B": [190, 180, 170],
        "C": [200, 190, 180],
        "D": [210, 200, 190],
    }
    first = score_spatial_quality(_panel(rows, start="2014-02-01 00:00:00"), _stations())
    second = score_spatial_quality(_panel(rows, start="2015-03-08 00:00:00"), _stations())
    assert first["suspect_spatiotemporal"].tolist() == second["suspect_spatiotemporal"].tolist()
    assert first["pm25_ug_m3"].tolist() == second["pm25_ug_m3"].tolist()


def test_trimmed_mean_drops_one_far_neighbor_and_does_not_impute():
    stats = aggregate_neighbors(np.array([3.0, 338.0, 420.0]), np.array([0.2, 0.5, 0.3]))
    assert stats["n_finite"] == 3
    assert stats["median"] == 338
    assert stats["trimmed_mean"] == (338 + 420) / 2
    assert stats["mean"] == float(np.mean([3, 338, 420]))
    assert stats["idw_mean"] == 0.2 * 3 + 0.5 * 338 + 0.3 * 420
    assert stats["idw_mean"] < stats["median"] < stats["trimmed_mean"]


def test_excluding_a_suspect_neighbor_does_not_rewrite_pm25():
    panel = _panel(
        {
            "A": [100, 100, 100],
            "B": [200, 3, 180],
            "C": [100, 100, 100],
            "D": [100, 100, 100],
        }
    )
    scored = attach_suspect_neighbor_influence(score_spatial_quality(panel, _stations()))
    origin = pd.Timestamp("2014-02-01 01:00:00")
    origin_rows = scored[scored["event_time_local"] == origin]
    suspect = origin_rows[origin_rows["station_name"] == "B"].iloc[0]
    host = origin_rows[origin_rows["station_name"] == "A"].iloc[0]
    assert suspect["pm25_ug_m3"] == 3
    assert suspect["suspect_spatiotemporal"]
    assert host["pm25_ug_m3"] == 100
    assert host["neighbor_suspect_count"] >= 1
    assert host["neighbor_idw_mean"] < host["neighbor_median"]
    assert np.isclose(host["neighbor_idw_excluding_suspect"], 100)
    assert np.isclose(host["neighbor_mean_excluding_suspect"], 100)


def test_neighbor_idw_matches_spatial_feature_mean():
    panel = _panel(
        {
            "A": [10, 20, 30],
            "B": [1, 2, 3],
            "C": [4, 5, 6],
            "D": [7, 8, 9],
        }
    )
    scored = score_spatial_quality(panel, _stations())
    featured, _ = add_spatial_features(panel, _stations(), n_neighbors=3)
    merged = scored.merge(
        featured[["station_name", "event_time_local", "neighbor_pm25_mean"]],
        on=["station_name", "event_time_local"],
    )
    np.testing.assert_allclose(
        merged["neighbor_idw_mean"].to_numpy(dtype=float),
        merged["neighbor_pm25_mean"].to_numpy(dtype=float),
    )
