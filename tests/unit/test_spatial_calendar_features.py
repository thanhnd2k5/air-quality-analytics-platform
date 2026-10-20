"""Leak checks for calendar and nearest-neighbor features (no database)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.forecasting.spatial_calendar import (
    add_calendar_features,
    add_spatial_features,
    statutory_heating_mask,
)


def _panel() -> tuple[pd.DataFrame, pd.DataFrame]:
    times = pd.date_range("2016-02-07 22:00:00", periods=6, freq="h")
    # A at the origin, B one degree north (~111 km), C one degree east.
    stations = pd.DataFrame(
        {
            "station_name": ["A", "B", "C"],
            "latitude": [40.0, 41.0, 40.0],
            "longitude": [116.0, 116.0, 117.0],
        }
    )
    rows = []
    values = {
        "A": [10, 10, 10, 10, 10, 999],
        "B": [1, 2, 30, 40, 50, 60],
        "C": [3, 4, 5, 6, 7, 8],
    }
    for name, series in values.items():
        for t, value in zip(times, series):
            rows.append(
                {
                    "station_key": {"A": 1, "B": 2, "C": 3}[name],
                    "station_name": name,
                    "event_time_local": t,
                    "pm25_ug_m3": value,
                }
            )
    return pd.DataFrame(rows), stations


def test_spatial_features_do_not_read_future_neighbor_pm25():
    df, stations = _panel()
    out, neighbors = add_spatial_features(df, stations, n_neighbors=2)
    # Origin hour 2016-02-08 02:00 is index of A where value is 10 and next hour is 999.
    # Neighbor mean at t must ignore 999.
    origin = pd.Timestamp("2016-02-08 02:00:00")
    row = out[(out["station_name"] == "A") & (out["event_time_local"] == origin)].iloc[0]
    assert row["pm25_ug_m3"] == 10
    assert row["neighbor_pm25_mean"] < 80
    assert row["neighbor_pm25_mean"] != 999
    # lag-1 is the previous clock hour, not the future spike
    assert row["neighbor_pm25_lag1"] < 80
    assert np.isfinite(row["neighbor_pm25_lag1"])
    assert 999 not in (
        row["neighbor_pm25_lag1"],
        row["neighbor_pm25_lag3"],
        row["neighbor_pm25_mean"],
    )
    assert set(neighbors["station_name"]) == {"A", "B", "C"}


def test_idw_uses_distance_and_clock_lag():
    df, stations = _panel()
    out, neighbors = add_spatial_features(df, stations, n_neighbors=2)
    origin = pd.Timestamp("2016-02-08 01:00:00")
    row = out[(out["station_name"] == "A") & (out["event_time_local"] == origin)].iloc[0]
    weights = neighbors[neighbors["station_name"] == "A"].set_index("neighbor_name")["weight"]
    b_t = 40
    c_t = 6
    expected = float(weights["B"] * b_t + weights["C"] * c_t)
    assert np.isclose(row["neighbor_pm25_mean"], expected)
    assert np.isclose(row["spatial_gradient"], 10 - expected)
    # One degree of longitude at 40N is shorter than one degree of latitude.
    assert weights["C"] > weights["B"]


def test_median_uses_the_same_neighbors_and_ignores_the_next_hour():
    times = pd.date_range("2016-12-20 14:00:00", periods=5, freq="h")
    stations = pd.DataFrame(
        {
            "station_name": ["A", "B", "C", "D"],
            "latitude": [40.00, 40.01, 40.02, 40.03],
            "longitude": [116.0, 116.0, 116.0, 116.0],
        }
    )
    values = {
        "A": [600, 628, 630, 640, 650],
        "B": [300, 338, 999, 340, 350],
        "C": [400, 420, 999, 430, 440],
        "D": [10, 3, 999, 20, 30],
    }
    rows = []
    for name, series in values.items():
        for time, value in zip(times, series):
            rows.append(
                {
                    "station_key": {"A": 1, "B": 2, "C": 3, "D": 4}[name],
                    "station_name": name,
                    "event_time_local": time,
                    "pm25_ug_m3": value,
                }
            )
    out, _ = add_spatial_features(pd.DataFrame(rows), stations, include_median=True)
    origin = pd.Timestamp("2016-12-20 15:00:00")
    row = out[(out["station_name"] == "A") & (out["event_time_local"] == origin)].iloc[0]
    assert row["neighbor_pm25_median"] == 338
    assert row["spatial_gradient_median"] == 628 - 338
    assert row["neighbor_n_finite"] == 3
    assert row["neighbor_pm25_mean"] < row["neighbor_pm25_median"]
    assert 999 not in (
        row["neighbor_pm25_median"],
        row["neighbor_pm25_median_lag1"],
        row["neighbor_pm25_median_lag3"],
        row["neighbor_pm25_mean"],
    )
    # One missing neighbor: median stays finite, same null rule as IDW.
    sparse = pd.DataFrame(rows)
    sparse.loc[
        sparse["station_name"].eq("D") & sparse["event_time_local"].eq(origin),
        "pm25_ug_m3",
    ] = np.nan
    sparse_out, _ = add_spatial_features(sparse, stations, include_median=True)
    sparse_row = sparse_out[
        sparse_out["station_name"].eq("A") & sparse_out["event_time_local"].eq(origin)
    ].iloc[0]
    assert sparse_row["neighbor_n_finite"] == 2
    assert sparse_row["neighbor_pm25_median"] == (338 + 420) / 2
    assert np.isfinite(sparse_row["neighbor_pm25_mean"])
    empty = sparse.copy()
    empty.loc[empty["event_time_local"].eq(origin) & empty["station_name"].ne("A"), "pm25_ug_m3"] = np.nan
    empty_out, _ = add_spatial_features(empty, stations, include_median=True)
    empty_row = empty_out[
        empty_out["station_name"].eq("A") & empty_out["event_time_local"].eq(origin)
    ].iloc[0]
    assert empty_row["neighbor_n_finite"] == 0
    assert np.isnan(empty_row["neighbor_pm25_median"])
    assert np.isnan(empty_row["neighbor_pm25_mean"])


def test_calendar_flags_match_beijing_windows():
    times = pd.to_datetime(
        [
            "2016-02-07 23:00:00",  # 除夕
            "2016-02-08 00:00:00",  # 初一 midnight
            "2016-02-08 12:00:00",
            "2016-02-06 12:00:00",  # makeup workday
            "2016-10-01 08:00:00",  # national day, not heating
            "2016-11-13 00:00:00",  # early heating start
            "2016-11-14 00:00:00",  # adjusted heating, before statutory day
            "2016-11-15 00:00:00",
            "2016-07-01 00:00:00",
            "2014-03-16 00:00:00",  # 2013-14 extension day
            "2014-03-18 00:00:00",
        ]
    )
    df = pd.DataFrame({"event_time_local": times})
    out = add_calendar_features(df)
    assert list(out["is_chinese_new_year"])[:3] == [1, 1, 1]
    assert out.loc[1, "hours_from_cny_midnight"] == 0
    assert out.loc[0, "hours_from_cny_midnight"] == -1
    assert out.loc[3, "is_makeup_workday"] == 1
    assert out.loc[3, "is_chinese_new_year"] == 0
    assert out.loc[4, "is_public_holiday"] == 1
    assert out.loc[4, "is_heating_season"] == 0
    assert list(out.loc[5:7, "is_heating_season"]) == [1, 1, 1]
    statutory = statutory_heating_mask(out["event_time_local"])
    assert list(statutory.iloc[5:8].astype(bool)) == [False, False, True]
    assert out.loc[8, "is_heating_season"] == 0
    assert pd.isna(out.loc[8, "hours_from_cny_midnight"])
    assert out.loc[9, "is_heating_season"] == 1
    assert out.loc[10, "is_heating_season"] == 0
