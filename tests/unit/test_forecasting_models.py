"""Unit tests for Phase 10c model helpers (no database)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.forecasting.constants import FEATURE_COLS, TARGET_COL
from src.forecasting.models import (
    choose_lock,
    compute_sample_weights,
    predict_persistence,
    run_persistence,
)


def _mini_matrix(n: int = 40) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    times = pd.date_range("2015-01-01", periods=n, freq="h")
    pm = rng.uniform(10, 100, size=n)
    df = pd.DataFrame(
        {
            "station_key": 1,
            "event_time_local": times,
            "target_time_local": times + pd.Timedelta(hours=1),
            "split": ["train"] * (n - 10) + ["val"] * 5 + ["test"] * 5,
            "pm25_ug_m3": pm,
            "pm25_lag_1": np.r_[np.nan, pm[:-1]],
            TARGET_COL: np.r_[pm[1:], np.nan],
            "hour": [t.hour for t in times],
            "month": [t.month for t in times],
            "day_of_week": [t.isoweekday() for t in times],
            "season_code": 0,
            "cluster_id": 0,
        }
    )
    # Fill remaining FEATURE_COLS with simple values
    for c in FEATURE_COLS:
        if c not in df.columns:
            if "missing" in c:
                df[c] = 0
            elif "roll" in c or "lag" in c:
                df[c] = df["pm25_lag_1"].fillna(pm.mean())
            elif c in ("temperature_c", "relative_humidity_pct", "wind_speed_m_s") or c.endswith(
                "_lag_1"
            ):
                df[c] = 10.0
            else:
                df[c] = 0
    df = df.dropna(subset=[TARGET_COL, "pm25_ug_m3", "pm25_lag_1"]).reset_index(drop=True)
    return df


def test_persistence_equals_pm25_at_t():
    df = _mini_matrix()
    preds = predict_persistence(df)
    np.testing.assert_allclose(preds, df["pm25_ug_m3"].to_numpy(dtype=float))
    # Must not silently use lag_1 (PM2.5 at t-1)
    assert not np.allclose(preds, df["pm25_lag_1"].to_numpy(dtype=float))


def test_choose_lock_picks_lower_val_mae():
    df = _mini_matrix()
    base = run_persistence(df)

    class _Fake:
        def __init__(self, name, val_mae):
            self.name = name
            self.metrics = {
                "train": {"mae": 1.0, "rmse": 1.0, "r2": 0.0},
                "val": {"mae": val_mae, "rmse": 1.0, "r2": 0.0},
                "test": {"mae": val_mae, "rmse": 1.0, "r2": 0.0},
            }
            self.predictions = base.predictions
            self.estimator = object()

    locked = choose_lock([base, _Fake("linear_regression", 5.0), _Fake("hist_gradient_boosting", 3.0)])
    assert locked.name == "hist_gradient_boosting"


def test_sample_weights_dirty_bin():
    pm = np.array([50.0, 120.0, 80.0])
    y = np.array([60.0, 90.0, 130.0])
    w = compute_sample_weights(pm, y, threshold=115.0, high_weight=2.0)
    np.testing.assert_allclose(w, [1.0, 2.0, 2.0])
