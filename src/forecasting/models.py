"""Baseline and ML models for Phase 10c."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.forecasting.constants import FEATURE_COLS, TARGET_COL
from src.forecasting.metrics import regression_metrics

RANDOM_STATE = 42

# Linear: one-hot categoricals; scale remaining numerics.
LINEAR_CAT_COLS = ("station_key", "season_code", "cluster_id", "in_episode_flag")
# HistGB: native categorical handling for low-cardinality ids.
HISTGB_CAT_COLS = (
    "station_key",
    "season_code",
    "cluster_id",
    "hour",
    "month",
    "day_of_week",
    "in_episode_flag",
)


@dataclass
class ModelResult:
    name: str
    predictions: pd.Series
    metrics: dict[str, dict[str, float]]
    estimator: Any | None = None


def _feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in FEATURE_COLS if c not in df.columns]
    if missing:
        raise KeyError(f"Missing feature columns: {missing}")
    return df.loc[:, list(FEATURE_COLS)].copy()


def predict_persistence(df: pd.DataFrame) -> np.ndarray:
    """y_hat(t+1) = PM2.5(t) on the engineered row (prediction origin time)."""
    return df["pm25_ug_m3"].to_numpy(dtype=float)


def build_linear_pipeline() -> Pipeline:
    cat = [c for c in LINEAR_CAT_COLS if c in FEATURE_COLS]
    num = [c for c in FEATURE_COLS if c not in cat]
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


def build_histgb() -> HistGradientBoostingRegressor:
    cat_idx = [FEATURE_COLS.index(c) for c in HISTGB_CAT_COLS if c in FEATURE_COLS]
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


def run_linear(train: pd.DataFrame, full: pd.DataFrame) -> ModelResult:
    pipe = build_linear_pipeline()
    x_train = _feature_frame(train)
    y_train = train[TARGET_COL].to_numpy(dtype=float)
    pipe.fit(x_train, y_train)
    preds = pipe.predict(_feature_frame(full))
    return ModelResult(
        name="linear_regression",
        predictions=pd.Series(preds, index=full.index, name="y_hat"),
        metrics=_metrics_for_splits(full, preds),
        estimator=pipe,
    )


def run_histgb(train: pd.DataFrame, full: pd.DataFrame) -> ModelResult:
    model = build_histgb()
    x_train = _feature_frame(train)
    y_train = train[TARGET_COL].to_numpy(dtype=float)
    # HistGB categorical_features needs integer codes; ensure int dtype
    for c in HISTGB_CAT_COLS:
        if c in x_train.columns:
            x_train[c] = x_train[c].astype(int)
    x_full = _feature_frame(full)
    for c in HISTGB_CAT_COLS:
        if c in x_full.columns:
            x_full[c] = x_full[c].astype(int)
    model.fit(x_train, y_train)
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
