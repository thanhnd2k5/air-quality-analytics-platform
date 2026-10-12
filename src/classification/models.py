"""Baselines and learned models for the PM2.5 alert classifier."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.tree import DecisionTreeClassifier

from src.classification.constants import (
    ALERT_TARGET_COL,
    ALERT_THRESHOLD,
    FEATURE_COLS,
    LOCK_METRIC,
    RANDOM_STATE,
    THRESHOLD_GRID,
    TREE_DEPTH_GRID,
    TREE_MIN_SAMPLES_LEAF,
)
from src.classification.metrics import classification_metrics, threshold_curve
from src.forecasting.models import HISTGB_CAT_COLS


@dataclass
class ClassifierResult:
    name: str
    pred: np.ndarray  # 0/1 for every row of the full frame
    proba: np.ndarray | None  # P(alert) when the model has one
    metrics: dict[str, dict[str, Any]]  # split → metrics
    threshold: float | None = None
    params: dict[str, Any] = field(default_factory=dict)
    estimator: Any | None = None


def feature_frame(df: pd.DataFrame, feature_cols: Sequence[str] = FEATURE_COLS) -> pd.DataFrame:
    missing = [c for c in feature_cols if c not in df.columns]
    if missing:
        raise KeyError(f"Missing feature columns: {missing}")
    x = df.loc[:, list(feature_cols)].copy()
    for c in HISTGB_CAT_COLS:
        if c in x.columns:
            x[c] = x[c].astype(int)
    return x


def metrics_by_split(df: pd.DataFrame, pred: np.ndarray, proba: np.ndarray | None) -> dict:
    out: dict[str, dict[str, Any]] = {}
    for split in ("train", "val", "test"):
        mask = (df["split"] == split).to_numpy()
        if not mask.any():
            continue
        out[split] = classification_metrics(
            df.loc[mask, ALERT_TARGET_COL],
            pred[mask],
            None if proba is None else proba[mask],
        )
    return out


def run_majority(df: pd.DataFrame) -> ClassifierResult:
    """Always predict the majority class of train (shows why accuracy alone misleads)."""
    train_y = df.loc[df["split"] == "train", ALERT_TARGET_COL]
    majority = int(train_y.mean() >= 0.5)
    pred = np.full(len(df), majority, dtype=int)
    return ClassifierResult(
        name="majority",
        pred=pred,
        proba=None,
        metrics=metrics_by_split(df, pred, None),
        params={"constant": majority},
    )


def run_persistence(df: pd.DataFrame, threshold: float = ALERT_THRESHOLD) -> ClassifierResult:
    """Alert next hour iff PM2.5 is already ≥ threshold now (what an operator does today)."""
    pred = (df["pm25_ug_m3"].to_numpy(dtype=float) >= threshold).astype(int)
    return ClassifierResult(
        name="persistence",
        pred=pred,
        proba=None,
        metrics=metrics_by_split(df, pred, None),
        params={"rule": f"pm25(t) >= {threshold}"},
    )


def tune_threshold(y_val, proba_val, grid: Sequence[float] = THRESHOLD_GRID) -> tuple[float, list]:
    """Pick the probability cut-off with the best val F1 (ties → closest to 0.5)."""
    curve = threshold_curve(y_val, proba_val, grid)
    best = max(curve, key=lambda r: (round(r["f1"], 6), -abs(r["threshold"] - 0.5)))
    return float(best["threshold"]), curve


def _finish(
    name: str,
    estimator,
    df: pd.DataFrame,
    x_full: pd.DataFrame,
    params: dict[str, Any],
) -> ClassifierResult:
    proba = estimator.predict_proba(x_full)[:, 1]
    val = (df["split"] == "val").to_numpy()
    threshold, curve = tune_threshold(df.loc[val, ALERT_TARGET_COL], proba[val])
    pred = (proba >= threshold).astype(int)
    return ClassifierResult(
        name=name,
        pred=pred,
        proba=proba,
        metrics=metrics_by_split(df, pred, proba),
        threshold=threshold,
        params={**params, "threshold_curve_val": curve},
        estimator=estimator,
    )


def run_decision_tree(
    df: pd.DataFrame,
    *,
    feature_cols: Sequence[str] = FEATURE_COLS,
    depth_grid: Sequence[int] = TREE_DEPTH_GRID,
) -> ClassifierResult:
    """Entropy (information-gain) tree; depth chosen by val F1 at cut-off 0.5."""
    train = (df["split"] == "train").to_numpy()
    val = (df["split"] == "val").to_numpy()
    x_full = feature_frame(df, feature_cols)
    y = df[ALERT_TARGET_COL].to_numpy(dtype=int)

    depth_scores = []
    best = None
    for depth in depth_grid:
        tree = DecisionTreeClassifier(
            criterion="entropy",
            max_depth=depth,
            min_samples_leaf=TREE_MIN_SAMPLES_LEAF,
            random_state=RANDOM_STATE,
        ).fit(x_full[train], y[train])
        val_pred = tree.predict(x_full[val])
        f1 = classification_metrics(y[val], val_pred)["f1"]
        depth_scores.append({"max_depth": depth, "val_f1_at_0.5": f1})
        if best is None or f1 > best[0]:
            best = (f1, depth, tree)

    _, depth, tree = best
    return _finish(
        "decision_tree",
        tree,
        df,
        x_full,
        {
            "criterion": "entropy",
            "max_depth": depth,
            "min_samples_leaf": TREE_MIN_SAMPLES_LEAF,
            "depth_search_val": depth_scores,
        },
    )


def run_histgb(
    df: pd.DataFrame,
    *,
    feature_cols: Sequence[str] = FEATURE_COLS,
) -> ClassifierResult:
    """Gradient-boosted trees; same hyper-parameters as the regression lock."""
    train = (df["split"] == "train").to_numpy()
    x_full = feature_frame(df, feature_cols)
    y = df[ALERT_TARGET_COL].to_numpy(dtype=int)
    cat_idx = [list(feature_cols).index(c) for c in HISTGB_CAT_COLS if c in feature_cols]
    params = {
        "max_depth": 8,
        "max_iter": 200,
        "learning_rate": 0.08,
        "min_samples_leaf": 40,
        "l2_regularization": 0.1,
    }
    model = HistGradientBoostingClassifier(
        **params,
        random_state=RANDOM_STATE,
        categorical_features=cat_idx,
    ).fit(x_full[train], y[train])
    return _finish("hist_gradient_boosting", model, df, x_full, params)


def choose_lock(results: list[ClassifierResult], metric: str = LOCK_METRIC) -> ClassifierResult:
    """Best val metric among learned models (baselines are only for comparison)."""
    learned = [r for r in results if r.estimator is not None]
    if not learned:
        raise ValueError("No learned models to lock")
    return max(learned, key=lambda r: r.metrics["val"][metric])
