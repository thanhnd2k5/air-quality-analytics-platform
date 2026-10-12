"""Error analysis helpers for locked PM2.5 forecast (Phase 10e)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.forecasting.constants import TARGET_COL
from src.forecasting.metrics import regression_metrics

ROOT = Path(__file__).resolve().parents[2]
PRED_PATH = ROOT / "artifacts" / "forecasting" / "predictions_locked.parquet"
STATION_MAP = ROOT / "data" / "clustering" / "station_cluster_assignment.csv"


def load_predictions_with_names(
    pred_path: Path | None = None,
) -> pd.DataFrame:
    path = pred_path or PRED_PATH
    if not path.is_file():
        # CSV fallback (v1/v2 scripts may write either)
        csv_path = path.with_suffix(".csv")
        if csv_path.is_file():
            path = csv_path
        else:
            raise FileNotFoundError(f"Missing {path}")
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
        df["event_time_local"] = pd.to_datetime(df["event_time_local"])
        df["target_time_local"] = pd.to_datetime(df["target_time_local"])
    else:
        df = pd.read_parquet(path)
    stations = pd.read_csv(STATION_MAP)[["station_key", "station_name", "district"]]
    return df.merge(stations, on="station_key", how="left")


def _mae(y_true, y_pred) -> float:
    return float(np.mean(np.abs(np.asarray(y_true) - np.asarray(y_pred))))


def summarize_by(
    df: pd.DataFrame,
    group_cols: list[str],
    *,
    y_col: str = TARGET_COL,
    pred_col: str = "y_hat_locked",
    base_col: str = "y_hat_persistence",
) -> pd.DataFrame:
    rows = []
    for keys, sub in df.groupby(group_cols, sort=True):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(group_cols, keys))
        row["n"] = int(len(sub))
        row["mae"] = _mae(sub[y_col], sub[pred_col])
        row["mae_persistence"] = _mae(sub[y_col], sub[base_col])
        row["mae_lift_vs_persistence"] = row["mae_persistence"] - row["mae"]
        row["mean_actual"] = float(sub[y_col].mean())
        rows.append(row)
    return pd.DataFrame(rows).sort_values("mae", ascending=False)


def worst_days(
    df: pd.DataFrame,
    *,
    top_n: int = 20,
    y_col: str = TARGET_COL,
    pred_col: str = "y_hat_locked",
) -> pd.DataFrame:
    tmp = df.copy()
    tmp["day"] = pd.to_datetime(tmp["target_time_local"]).dt.floor("D")
    g = (
        tmp.groupby(["day", "station_key", "station_name"], as_index=False)
        .agg(
            n=("abs_error_locked", "size"),
            mae=("abs_error_locked", "mean"),
            max_abs_error=("abs_error_locked", "max"),
            mean_actual=(y_col, "mean"),
            mean_pred=(pred_col, "mean"),
        )
        .sort_values("mae", ascending=False)
        .head(top_n)
    )
    return g


def residual_bins(
    df: pd.DataFrame,
    *,
    y_col: str = TARGET_COL,
    pred_col: str = "y_hat_locked",
    bins: list[float] | None = None,
) -> pd.DataFrame:
    bins = bins or [0, 35, 75, 115, 150, 250, 500, 1000]
    tmp = df.copy()
    tmp["actual_bin"] = pd.cut(tmp[y_col], bins=bins, right=False)
    tmp["residual"] = tmp[pred_col] - tmp[y_col]
    rows = []
    for b, sub in tmp.groupby("actual_bin", observed=False):
        if len(sub) == 0:
            continue
        rows.append(
            {
                "actual_bin": str(b),
                "n": int(len(sub)),
                "mae": float(sub["abs_error_locked"].mean()),
                "mean_residual": float(sub["residual"].mean()),
                "mean_actual": float(sub[y_col].mean()),
            }
        )
    return pd.DataFrame(rows)


def build_error_report_tables(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    test = df[df["split"] == "test"].copy()
    if test.empty:
        raise ValueError("No test rows in predictions")
    return {
        "overall_by_split": summarize_by(df, ["split"]),
        "test_by_station": summarize_by(test, ["station_key", "station_name", "cluster_label"]),
        "test_by_cluster": summarize_by(test, ["cluster_id", "cluster_label"]),
        "test_by_season": summarize_by(test, ["season"]),
        "test_by_hour": summarize_by(test, ["hour"]),
        "test_worst_days": worst_days(test),
        "test_residual_by_actual_bin": residual_bins(test),
    }


def overall_test_metrics(df: pd.DataFrame) -> dict[str, Any]:
    test = df[df["split"] == "test"]
    locked = regression_metrics(test[TARGET_COL], test["y_hat_locked"])
    base = regression_metrics(test[TARGET_COL], test["y_hat_persistence"])
    return {
        "n_test": int(len(test)),
        "locked": locked,
        "persistence": base,
        "mae_lift": float(base["mae"] - locked["mae"]),
    }
