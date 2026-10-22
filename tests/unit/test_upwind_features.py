"""Convention checks for upwind weights. No database and no Dec 2016 rows."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.forecasting.upwind import UPWIND_WEAK_WIND_M_S, add_upwind_features


def _panel(azimuth: float, speed: float) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    stations = pd.DataFrame(
        {
            "station_name": ["A", "B", "C"],
            "latitude": [40.0, 41.0, 39.0],
            "longitude": [116.0, 116.0, 116.0],
        }
    )
    t0 = pd.Timestamp("2015-06-01 12:00:00")
    rows = []
    # B is due north of A, C is due south. Values at t-1 and t.
    series = {
        "A": [10.0, 10.0],
        "B": [30.0, 40.0],
        "C": [7.0, 5.0],
    }
    wind_rows = []
    for name, values in series.items():
        for shift, value in enumerate(values):
            when = t0 + pd.Timedelta(hours=shift - 1)
            rows.append(
                {
                    "station_key": {"A": 1, "B": 2, "C": 3}[name],
                    "station_name": name,
                    "event_time_local": when,
                    "pm25_ug_m3": value,
                    "wind_speed_m_s": speed,
                }
            )
            wind_rows.append(
                {
                    "station_name": name,
                    "event_time_local": when,
                    "azimuth_deg": azimuth,
                }
            )
    return pd.DataFrame(rows), stations, pd.DataFrame(wind_rows)


def test_wind_from_north_selects_the_northern_station():
    df, stations, wind = _panel(0.0, 3.0)
    out = add_upwind_features(df, stations, wind)
    row = out[(out["station_name"] == "A") & (out["event_time_local"] == "2015-06-01 12:00:00")].iloc[0]
    assert np.isclose(row["upwind_pm25"], 40.0)
    assert np.isclose(row["upwind_pm25_lag1"], 30.0)
    assert np.isclose(row["upwind_minus_local"], 30.0)
    assert row["upwind_weak_wind"] == 0
    assert row["upwind_unavailable"] == 0
    assert row["upwind_pm25"] != 5.0


def test_wind_from_south_selects_the_southern_station():
    df, stations, wind = _panel(180.0, 3.0)
    out = add_upwind_features(df, stations, wind)
    row = out[(out["station_name"] == "A") & (out["event_time_local"] == "2015-06-01 12:00:00")].iloc[0]
    assert np.isclose(row["upwind_pm25"], 5.0)
    assert np.isclose(row["upwind_pm25_lag1"], 7.0)


def test_weak_wind_suppresses_upwind_concentration():
    df, stations, wind = _panel(0.0, UPWIND_WEAK_WIND_M_S - 0.2)
    out = add_upwind_features(df, stations, wind)
    row = out[(out["station_name"] == "A") & (out["event_time_local"] == "2015-06-01 12:00:00")].iloc[0]
    assert pd.isna(row["upwind_pm25"])
    assert row["upwind_weak_wind"] == 1
    assert row["upwind_unavailable"] == 0


def test_missing_direction_is_unavailable_not_a_downwind_zero():
    df, stations, wind = _panel(np.nan, 3.0)
    out = add_upwind_features(df, stations, wind)
    row = out[(out["station_name"] == "A") & (out["event_time_local"] == "2015-06-01 12:00:00")].iloc[0]
    assert pd.isna(row["upwind_pm25"])
    assert row["upwind_unavailable"] == 1
