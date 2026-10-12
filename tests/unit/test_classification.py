"""Unit tests for the PM2.5 alert classifier (no database)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.classification.constants import ALERT_TARGET_COL, ALERT_THRESHOLD, FEATURE_COLS
from src.classification.metrics import classification_metrics, mcnemar, onset_recall
from src.classification.models import (
    choose_lock,
    run_decision_tree,
    run_majority,
    run_persistence,
    tune_threshold,
)
from src.classification.target import add_alert_target, alert_label
from src.forecasting.constants import TARGET_COL


def _matrix(n_per_split: int = 120, seed: int = 0) -> pd.DataFrame:
    """One station, hourly, smooth PM2.5 that crosses 115 often."""
    rng = np.random.default_rng(seed)
    n = 3 * n_per_split
    times = pd.date_range("2015-01-01", periods=n, freq="h")
    pm = 115 + 80 * np.sin(np.arange(n) / 6.0) + rng.normal(0, 5, n)
    pm = np.clip(pm, 1, None)
    df = pd.DataFrame(
        {
            "station_key": 1,
            "event_time_local": times,
            "target_time_local": times + pd.Timedelta(hours=1),
            "split": ["train"] * n_per_split + ["val"] * n_per_split + ["test"] * n_per_split,
            "pm25_ug_m3": pm,
            TARGET_COL: np.r_[pm[1:], np.nan],
        }
    )
    for c in FEATURE_COLS:
        if c not in df.columns:
            df[c] = 0
    df["pm25_delta_1"] = np.r_[0.0, np.diff(pm)]
    return df.iloc[:-1].reset_index(drop=True)


def test_alert_label_threshold_is_inclusive():
    assert alert_label([114.9, 115.0, 200.0]).tolist() == [0, 1, 1]


def test_target_h1_reuses_regression_target():
    df = add_alert_target(_matrix(), horizon=1)
    expected = (df[TARGET_COL] >= ALERT_THRESHOLD).astype(int)
    assert (df[ALERT_TARGET_COL] == expected).all()


def test_target_longer_horizon_looks_up_future_hour():
    m = _matrix()
    df = add_alert_target(m, horizon=3)
    row = df.iloc[10]
    future = m.loc[m["event_time_local"] == row["event_time_local"] + pd.Timedelta(hours=3), "pm25_ug_m3"]
    assert row["y_pm25_target"] == pytest.approx(float(future.iloc[0]))
    assert (df["target_time_local"] - df["event_time_local"]).eq(pd.Timedelta(hours=3)).all()


def test_target_rejects_non_positive_horizon():
    with pytest.raises(ValueError):
        add_alert_target(_matrix(), horizon=0)


def test_metrics_confusion_counts():
    m = classification_metrics([1, 1, 0, 0, 1], [1, 0, 0, 1, 1])
    assert (m["tp"], m["fn"], m["tn"], m["fp"]) == (2, 1, 1, 1)
    assert m["precision"] == pytest.approx(2 / 3)
    assert m["recall"] == pytest.approx(2 / 3)


def test_onset_recall_persistence_is_zero():
    pm_now = np.array([100, 120, 90, 130])
    y = np.array([1, 1, 1, 0])
    persistence = (pm_now >= ALERT_THRESHOLD).astype(int)
    on = onset_recall(pm_now, y, persistence, ALERT_THRESHOLD)
    assert on["onsets"] == 2 and on["recall"] == 0.0


def test_mcnemar_identical_predictions():
    out = mcnemar([1, 0, 1], [1, 0, 0], [1, 0, 0])
    assert out["b"] == 0 and out["c"] == 0 and out["p_value"] == 1.0


def test_tune_threshold_picks_best_f1():
    y = np.array([0, 0, 1, 1])
    proba = np.array([0.1, 0.35, 0.4, 0.9])
    t, curve = tune_threshold(y, proba, grid=(0.3, 0.38, 0.5))
    assert t == 0.38
    assert len(curve) == 3


def test_baselines_and_lock_use_val_only():
    df = add_alert_target(_matrix(), horizon=1)
    majority = run_majority(df)
    persistence = run_persistence(df)
    tree = run_decision_tree(df, depth_grid=(2, 3))
    assert majority.metrics["test"]["recall"] in (0.0, 1.0)
    assert set(persistence.metrics) == {"train", "val", "test"}
    assert tree.threshold is not None
    # Lock ignores baselines and is decided on val.
    assert choose_lock([majority, persistence, tree]).name == "decision_tree"
    assert tree.params["max_depth"] in (2, 3)
