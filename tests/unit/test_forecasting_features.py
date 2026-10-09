"""Unit tests for Phase 10b lag/target/split (no database)."""

from __future__ import annotations

import pandas as pd
import pytest

from src.forecasting.constants import TARGET_COL
from src.forecasting.features import (
    add_pm25_lags_and_rolls,
    add_target,
    build_feature_matrix,
    drop_unusable_rows,
)
from src.forecasting.split import assign_split


def _toy_station(
    pm25: list[float | None],
    *,
    station_key: int = 1,
    start: str = "2015-01-01 00:00:00",
) -> pd.DataFrame:
    times = pd.date_range(start, periods=len(pm25), freq="h")
    n = len(pm25)
    return pd.DataFrame(
        {
            "station_key": station_key,
            "event_time_local": times,
            "hour": [t.hour for t in times],
            "month": [t.month for t in times],
            "day_of_week": [t.isoweekday() for t in times],
            "season": ["winter"] * n,
            "pm25_ug_m3": pm25,
            "temperature_c": [10.0] * n,
            "relative_humidity_pct": [50.0] * n,
            "wind_speed_m_s": [2.0] * n,
            "cluster_id": 0,
            "cluster_label": "elevated_core",
        }
    )


def test_lag1_is_previous_hour_not_future():
    df = _toy_station([10.0, 20.0, 30.0, 40.0])
    out = add_pm25_lags_and_rolls(df)
    assert pd.isna(out.loc[0, "pm25_lag_1"])
    assert out.loc[1, "pm25_lag_1"] == 10.0
    assert out.loc[2, "pm25_lag_1"] == 20.0
    assert out.loc[2, "pm25_lag_1"] != out.loc[2, "pm25_ug_m3"]


def test_target_is_next_hour_pm25():
    df = _toy_station([10.0, 20.0, 30.0, 40.0])
    out = add_target(df)
    assert out.loc[0, TARGET_COL] == 20.0
    assert out.loc[1, TARGET_COL] == 30.0
    assert pd.isna(out.loc[3, TARGET_COL])
    assert out.loc[0, "target_time_local"] == out.loc[0, "event_time_local"] + pd.Timedelta(
        hours=1
    )


def test_rolling_mean_does_not_use_future():
    df = _toy_station([1.0, 2.0, 3.0, 100.0])
    out = add_pm25_lags_and_rolls(df)
    # At index 2 (value 3), roll-3 ending at t = mean(1,2,3)=2 — must not include 100
    # We use window 6 with min_periods; check roll_mean_6 at last-but-one vs last
    # Explicit: rolling at t=2 should be mean of [1,2,3] for window covering those
    # With window=6 min_periods=3: at idx 2 → mean(1,2,3)=2.0
    assert out.loc[2, "pm25_roll_mean_6"] == pytest.approx(2.0)
    assert out.loc[3, "pm25_roll_mean_6"] == pytest.approx((1 + 2 + 3 + 100) / 4)


def test_assign_split_chronological():
    times = pd.to_datetime(
        [
            "2014-06-01 00:00:00",
            "2016-03-01 00:00:00",
            "2016-09-01 00:00:00",
            "2017-01-15 00:00:00",
        ]
    )
    splits = assign_split(pd.Series(times))
    assert list(splits) == ["train", "val", "test", pd.NA]


def test_drop_requires_target_current_pm25_and_lags():
    df = _toy_station([float(i) for i in range(30)])
    df = add_pm25_lags_and_rolls(df)
    df = add_target(df)
    kept = drop_unusable_rows(df)
    assert TARGET_COL in kept.columns
    assert kept["pm25_ug_m3"].notna().all()
    assert kept["pm25_lag_1"].notna().all()
    assert kept["pm25_lag_24"].notna().all()
    assert kept[TARGET_COL].notna().all()
    # First 24 rows lack lag_24; last row lacks target → fewer than 30
    assert len(kept) < 30
    assert len(kept) >= 5


def test_weather_impute_uses_train_median_only():
    # Need ≥24h history per split segment so lag/roll rows survive the drop gate.
    rows = []
    for start, n, temp in [
        ("2015-01-01", 48, 10.0),
        ("2016-03-01", 48, 20.0),
        ("2016-09-01", 48, 30.0),
    ]:
        part = _toy_station([50.0] * n, start=start)
        part["temperature_c"] = temp
        rows.append(part)
    base = pd.concat(rows, ignore_index=True)
    # Punch NaN in val/test weather
    base.loc[base["event_time_local"] >= "2016-01-01", "temperature_c"] = None

    matrix, meta = build_feature_matrix(base)
    assert meta["weather_train_medians"]["temperature_c"] == pytest.approx(10.0)
    # Val/test filled with train median 10, not 20/30
    assert (matrix.loc[matrix["split"] != "train", "temperature_c"] == 10.0).all()


def test_lags_isolated_per_station():
    a = _toy_station([1.0, 2.0, 3.0], station_key=1)
    b = _toy_station([10.0, 20.0, 30.0], station_key=2)
    df = pd.concat([a, b], ignore_index=True)
    out = add_pm25_lags_and_rolls(df)
    # First row of station 2 must not get station 1's last value as lag1
    b0 = out[out["station_key"] == 2].iloc[0]
    assert pd.isna(b0["pm25_lag_1"])
