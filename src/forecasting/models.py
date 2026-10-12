"""Baseline and ML models for Phase 10c / Vòng A HistGB v2."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.forecasting.constants import (
    FEATURE_COLS,
    SAMPLE_WEIGHT_HIGH,
    SAMPLE_WEIGHT_THRESHOLD,
    TARGET_COL,
)
from src.forecasting.metrics import regression_metrics

RANDOM_STATE = 42

# Linear: one-hot categoricals; scale remaining numerics.
LINEAR_CAT_COLS = ("station_key", "season_code", "cluster_id")
# HistGB: native categorical handling for low-cardinality ids.
HISTGB_CAT_COLS = ("station_key", "season_code", "cluster_id", "hour", "month", "day_of_week")


@dataclass
class ModelResult:
    name: str
    predictions: pd.Series
    metrics: dict[str, dict[str, float]]
    estimator: Any | None = None


def _feature_frame(
    df: pd.DataFrame,
    feature_cols: Sequence[str] = FEATURE_COLS,
) -> pd.DataFrame:
    missing = [c for c in feature_cols if c not in df.columns]
    if missing:
        raise KeyError(f"Missing feature columns: {missing}")
    return df.loc[:, list(feature_cols)].copy()


def predict_persistence(df: pd.DataFrame) -> np.ndarray:
    """y_hat(t+1) = PM2.5(t) on the engineered row (prediction origin time)."""
    return df["pm25_ug_m3"].to_numpy(dtype=float)


def compute_sample_weights(
    pm25_t: np.ndarray | pd.Series,
    y: np.ndarray | pd.Series,
    *,
    threshold: float = SAMPLE_WEIGHT_THRESHOLD,
    high_weight: float = SAMPLE_WEIGHT_HIGH,
) -> np.ndarray:
    """Higher weight when origin PM2.5 or target is in the dirty bin (≥ threshold)."""
    pm = np.asarray(pm25_t, dtype=float)
    target = np.asarray(y, dtype=float)
    dirty = (pm >= threshold) | (target >= threshold)
    return np.where(dirty, high_weight, 1.0).astype(float)


def build_linear_pipeline(
    feature_cols: Sequence[str] = FEATURE_COLS,
) -> Pipeline:
    cat = [c for c in LINEAR_CAT_COLS if c in feature_cols]
    num = [c for c in feature_cols if c not in cat]
    pre = ColumnTransformer(
        transformers=[
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                list(cat),
            ),
            ("num", StandardScaler(), list(num)),
        ]
    )
    return Pipeline(
        steps=[
            ("pre", pre),
            ("model", LinearRegression()),
        ]
    )


def build_histgb(
    feature_cols: Sequence[str] = FEATURE_COLS,
) -> HistGradientBoostingRegressor:
    cat_idx = [list(feature_cols).index(c) for c in HISTGB_CAT_COLS if c in feature_cols]
    return HistGradientBoostingRegressor(
        max_depth=8,
        max_iter=200,
        learning_rate=0.08,
        min_samples_leaf=40,
        l2_regularization=0.1,
        random_state=RANDOM_STATE,
        categorical_features=cat_idx,
    )


def _metrics_for_splits(
    df: pd.DataFrame,
    preds: np.ndarray,
) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    tmp = df[[TARGET_COL, "split"]].copy()
    tmp["pred"] = preds
    for split, sub in tmp.groupby("split", sort=False):
        out[str(split)] = regression_metrics(sub[TARGET_COL], sub["pred"])
    return out


def run_persistence(df: pd.DataFrame) -> ModelResult:
    preds = predict_persistence(df)
    return ModelResult(
        name="persistence",
        predictions=pd.Series(preds, index=df.index, name="y_hat"),
        metrics=_metrics_for_splits(df, preds),
        estimator=None,
    )


def run_linear(
    train: pd.DataFrame,
    full: pd.DataFrame,
    *,
    feature_cols: Sequence[str] = FEATURE_COLS,
) -> ModelResult:
    pipe = build_linear_pipeline(feature_cols)
    x_train = _feature_frame(train, feature_cols)
    y_train = train[TARGET_COL].to_numpy(dtype=float)
    pipe.fit(x_train, y_train)
    preds = pipe.predict(_feature_frame(full, feature_cols))
    return ModelResult(
        name="linear_regression",
        predictions=pd.Series(preds, index=full.index, name="y_hat"),
        metrics=_metrics_for_splits(full, preds),
        estimator=pipe,
    )


def run_histgb(
    train: pd.DataFrame,
    full: pd.DataFrame,
    *,
    feature_cols: Sequence[str] = FEATURE_COLS,
    sample_weight: np.ndarray | None = None,
) -> ModelResult:
    model = build_histgb(feature_cols)
    x_train = _feature_frame(train, feature_cols)
    y_train = train[TARGET_COL].to_numpy(dtype=float)
    # HistGB categorical_features needs integer codes; ensure int dtype
    for c in HISTGB_CAT_COLS:
        if c in x_train.columns:
            x_train[c] = x_train[c].astype(int)
    x_full = _feature_frame(full, feature_cols)
    for c in HISTGB_CAT_COLS:
        if c in x_full.columns:
            x_full[c] = x_full[c].astype(int)
    if sample_weight is None:
        model.fit(x_train, y_train)
    else:
        model.fit(x_train, y_train, sample_weight=sample_weight)
    preds = model.predict(x_full)
    return ModelResult(
        name="hist_gradient_boosting",
        predictions=pd.Series(preds, index=full.index, name="y_hat"),
        metrics=_metrics_for_splits(full, preds),
        estimator=model,
    )


def choose_lock(
    results: list[ModelResult],
    *,
    primary_split: str = "val",
    metric: str = "mae",
) -> ModelResult:
    """Lock the model with best (lowest) primary metric on validation."""
    scored = []
    for r in results:
        if r.name == "persistence":
            continue
        scored.append((r.metrics[primary_split][metric], r.name, r))
    if not scored:
        raise ValueError("No ML models to lock")
    scored.sort(key=lambda t: t[0])
    return scored[0][2]
