"""Evaluation metrics for PM2.5 forecasting."""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


def regression_metrics(y_true, y_pred) -> dict[str, float]:
    """Primary MAE; secondary RMSE and R²."""
    yt = np.asarray(y_true, dtype=float)
    yp = np.asarray(y_pred, dtype=float)
    return {
        "mae": float(mean_absolute_error(yt, yp)),
        "rmse": float(np.sqrt(mean_squared_error(yt, yp))),
        "r2": float(r2_score(yt, yp)),
    }


def metrics_by_split(
    frame,
    *,
    y_col: str,
    pred_col: str,
    split_col: str = "split",
) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for split, sub in frame.groupby(split_col, sort=False):
        out[str(split)] = regression_metrics(sub[y_col], sub[pred_col])
    return out


def format_metrics_row(model: str, split: str, m: dict[str, float]) -> dict[str, Any]:
    return {
        "model": model,
        "split": split,
        "mae": m["mae"],
        "rmse": m["rmse"],
        "r2": m["r2"],
    }
