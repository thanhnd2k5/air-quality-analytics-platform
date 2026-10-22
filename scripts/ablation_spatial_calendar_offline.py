#!/usr/bin/env python3
"""Offline ablation: HistGB v2 vs calendar, spatial, and both.

Does not touch the model lock, warehouse, or FEATURE_COLS_V2.
Same split, hyperparameters, and sample weights as the v2 lock.
Same rows for M0–M3. Spatial features use PM2.5 at origin t or earlier only.

Example:
    py -3 scripts/ablation_spatial_calendar_offline.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.forecasting.constants import (  # noqa: E402
    EPISODE_MIN_HOURS,
    EPISODE_THRESHOLD,
    FEATURE_COLS_V2,
    SAMPLE_WEIGHT_HIGH,
    SAMPLE_WEIGHT_THRESHOLD,
    TARGET_COL,
    TEST_END,
    TEST_START,
    TRAIN_END,
    VAL_END,
    VAL_START,
)
from src.forecasting.metrics import regression_metrics  # noqa: E402
from src.forecasting.models import (  # noqa: E402
    RANDOM_STATE,
    compute_sample_weights,
    run_histgb,
)
from src.forecasting.spatial_calendar import (  # noqa: E402
    CALENDAR_FEATURES,
    SPATIAL_FEATURES,
    add_calendar_features,
    add_spatial_features,
    statutory_heating_mask,
)

OUT = ROOT / "artifacts" / "forecasting" / "spatial_calendar_ablation"
MATRIX_PARQUET = ROOT / "artifacts" / "forecasting" / "feature_matrix_v2.parquet"
STATION_MAP = ROOT / "data" / "clustering" / "station_cluster_assignment.csv"
STATIONS = ROOT / "data" / "raw" / "reference" / "stations.csv"

# Same numeric bar as the PBL ablation, fixed before fitting M1–M3.
PROMOTE_CRITERIA = {
    "rule": (
        "PROMOTE_CANDIDATE only if val AND test ΔMAE(model−M0) ≤ −0.15 µg/m³, "
        "winter-test and highPM-test do not worsen by >0.10, "
        "and ≥7/12 stations improve on test. "
        "WINTER_ONLY if winter-test ΔMAE ≤ −0.15 but the promote gate fails. "
        "Otherwise KEEP_BASELINE. The model lock is not updated either way."
    ),
    "delta_mae_improve_threshold": -0.15,
    "no_harm_threshold": 0.10,
    "min_stations_improved_on_test": 7,
    "high_pm_threshold": 115.0,
    "rapid_rise_ug_m3": 20.0,
}

MODELS = ("m0", "m1", "m2", "m3")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _finite(x: Any) -> float | None:
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if np.isnan(f) or np.isinf(f):
        return None
    return f


def _load_frame() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not MATRIX_PARQUET.exists():
        raise FileNotFoundError(f"Missing {MATRIX_PARQUET}")
    df = pd.read_parquet(MATRIX_PARQUET)
    df["event_time_local"] = pd.to_datetime(df["event_time_local"])
    df["station_key"] = df["station_key"].astype(int)
    names = pd.read_csv(STATION_MAP)[["station_key", "station_name"]]
    names["station_key"] = names["station_key"].astype(int)
    df = df.merge(names, on="station_key", how="left")
    if df["station_name"].isna().any():
        raise KeyError("station_key missing from cluster assignment")
    stations = pd.read_csv(STATIONS)
    df, neighbors = add_spatial_features(df, stations)
    df = add_calendar_features(df)
    return df, neighbors


def _peak_mask(df: pd.DataFrame) -> pd.Series:
    """Hour of max actual PM2.5 inside each post-hoc episode. Not a feature."""
    flag = pd.Series(False, index=df.index)
    ordered = df.sort_values(["station_key", "target_time_local"])
    for _, block in ordered.groupby("station_key", sort=False):
        y = block[TARGET_COL].to_numpy(dtype=float)
        times = pd.to_datetime(block["target_time_local"]).to_numpy()
        labels = block.index.to_numpy()
        dirty = np.isfinite(y) & (y >= EPISODE_THRESHOLD)
        start = 0
        while start < len(block):
            if not dirty[start]:
                start += 1
                continue
            end = start
            while end + 1 < len(block) and dirty[end + 1]:
                if times[end + 1] - times[end] != np.timedelta64(1, "h"):
                    break
                end += 1
            if end - start + 1 >= EPISODE_MIN_HOURS:
                local = int(np.nanargmax(y[start : end + 1]))
                flag.loc[labels[start + local]] = True
            start = end + 1
    return flag


def _metrics(y: pd.Series, pred: pd.Series) -> dict[str, float]:
    return regression_metrics(y, pred)


def _decide(delta: dict[str, float | None], n_improved: int) -> str:
    thr = PROMOTE_CRITERIA["delta_mae_improve_threshold"]
    harm = PROMOTE_CRITERIA["no_harm_threshold"]
    min_st = PROMOTE_CRITERIA["min_stations_improved_on_test"]
    needed = ("val", "test", "winter_test", "high_pm_test")
    if any(delta.get(k) is None for k in needed):
        return "KEEP_BASELINE"
    promote = (
        delta["val"] <= thr
        and delta["test"] <= thr
        and delta["winter_test"] <= harm
        and delta["high_pm_test"] <= harm
        and n_improved >= min_st
    )
    if promote:
        return "PROMOTE_CANDIDATE"
    if delta["winter_test"] <= thr:
        return "WINTER_ONLY"
    return "KEEP_BASELINE"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    started = _utc_now()
    frame, neighbors = _load_frame()
    neighbors.to_csv(OUT / "nearest_neighbors.csv", index=False)

    train = frame[frame["split"] == "train"].copy()
    if train.empty:
        raise RuntimeError("Empty train split")
    weights = compute_sample_weights(train["pm25_ug_m3"], train[TARGET_COL])

    feature_sets = {
        "m0": list(FEATURE_COLS_V2),
        "m1": [*FEATURE_COLS_V2, *CALENDAR_FEATURES],
        "m2": [*FEATURE_COLS_V2, *SPATIAL_FEATURES],
        "m3": [*FEATURE_COLS_V2, *CALENDAR_FEATURES, *SPATIAL_FEATURES],
    }
    preds: dict[str, np.ndarray] = {}
    for name, cols in feature_sets.items():
        print(f"Training {name} on {len(train)} rows, {len(cols)} features ...", flush=True)
        result = run_histgb(train, frame, feature_cols=cols, sample_weight=weights)
        preds[name] = result.predictions.to_numpy()

    eval_df = frame[
        [
            "station_key",
            "station_name",
            "event_time_local",
            "target_time_local",
            "split",
            "season",
            "pm25_ug_m3",
            TARGET_COL,
            "cluster_label",
            *CALENDAR_FEATURES,
            *SPATIAL_FEATURES,
        ]
    ].copy()
    for name in MODELS:
        eval_df[f"y_hat_{name}"] = preds[name]
        eval_df[f"abs_err_{name}"] = (eval_df[TARGET_COL] - eval_df[f"y_hat_{name}"]).abs()
        eval_df[f"signed_{name}"] = eval_df[f"y_hat_{name}"] - eval_df[TARGET_COL]

    eval_df["winter"] = eval_df["season"].astype(str).str.lower().eq("winter")
    eval_df["heating_statutory"] = statutory_heating_mask(eval_df["event_time_local"])
    eval_df["heating_adjusted"] = eval_df["is_heating_season"].eq(1)
    eval_df["rapid_rise"] = (eval_df[TARGET_COL] - eval_df["pm25_ug_m3"]) >= PROMOTE_CRITERIA["rapid_rise_ug_m3"]
    eval_df["episode_peak"] = _peak_mask(eval_df)
    high_pm = eval_df[TARGET_COL] >= PROMOTE_CRITERIA["high_pm_threshold"]

    masks = {
        "overall": pd.Series(True, index=eval_df.index),
        "winter": eval_df["winter"],
        "heating_statutory": eval_df["heating_statutory"],
        "heating_adjusted": eval_df["heating_adjusted"],
        "high_pm": high_pm,
        "rapid_rise": eval_df["rapid_rise"],
        "episode_peak": eval_df["episode_peak"],
        "cny": eval_df["is_chinese_new_year"].eq(1),
    }

    def block(mask: pd.Series) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for split in ("train", "val", "test"):
            sub = eval_df[mask & eval_df["split"].eq(split)]
            cell: dict[str, Any] = {"n": int(len(sub))}
            if sub.empty:
                for name in MODELS:
                    cell[name] = None
                cell["delta_mae"] = {name: None for name in MODELS if name != "m0"}
                out[split] = cell
                continue
            for name in MODELS:
                cell[name] = _metrics(sub[TARGET_COL], sub[f"y_hat_{name}"])
                cell[name]["mean_signed_error"] = float(sub[f"signed_{name}"].mean())
            cell["delta_mae"] = {
                name: _finite(cell[name]["mae"] - cell["m0"]["mae"]) for name in MODELS if name != "m0"
            }
            out[split] = cell
        return out

    metrics = {name: block(mask) for name, mask in masks.items()}

    test = eval_df[eval_df["split"].eq("test")]
    station_rows = []
    for station, sub in test.groupby("station_name", sort=True):
        row: dict[str, Any] = {
            "station_name": station,
            "cluster_label": str(sub["cluster_label"].iloc[0]),
            "n": int(len(sub)),
        }
        m0_mae = float(sub["abs_err_m0"].mean())
        row["mae_m0"] = m0_mae
        for name in ("m1", "m2", "m3"):
            mae = float(sub[f"abs_err_{name}"].mean())
            row[f"mae_{name}"] = mae
            row[f"delta_mae_{name}"] = mae - m0_mae
        winter_sub = sub[sub["winter"]]
        row["n_winter"] = int(len(winter_sub))
        if len(winter_sub):
            base = float(winter_sub["abs_err_m0"].mean())
            row["mae_m0_winter"] = base
            for name in ("m1", "m2", "m3"):
                mae = float(winter_sub[f"abs_err_{name}"].mean())
                row[f"delta_mae_{name}_winter"] = mae - base
        station_rows.append(row)
    stations_df = pd.DataFrame(station_rows)
    improved = {
        name: int((stations_df[f"delta_mae_{name}"] < 0).sum()) for name in ("m1", "m2", "m3")
    }

    decisions = {}
    for name in ("m1", "m2", "m3"):
        delta = {
            "val": metrics["overall"]["val"]["delta_mae"][name],
            "test": metrics["overall"]["test"]["delta_mae"][name],
            "winter_test": metrics["winter"]["test"]["delta_mae"][name],
            "high_pm_test": metrics["high_pm"]["test"]["delta_mae"][name],
        }
        decisions[name] = {
            "decision": _decide(delta, improved[name]),
            "delta_mae": delta,
            "stations_improved_test": improved[name],
        }

    null_spatial = {
        col: int(frame[col].isna().sum()) for col in SPATIAL_FEATURES
    }
    null_cny_hours = int(frame["hours_from_cny_midnight"].isna().sum())

    report = {
        "ok": True,
        "phase": "spatial_calendar_offline_ablation",
        "started_at": started,
        "finished_at": _utc_now(),
        "locked_reference": {
            "algorithm": "hist_gradient_boosting",
            "random_state": RANDOM_STATE,
            "model_lock_untouched": True,
            "feature_sets": {k: v for k, v in feature_sets.items()},
            "sample_weight": {
                "threshold": SAMPLE_WEIGHT_THRESHOLD,
                "high_weight": SAMPLE_WEIGHT_HIGH,
            },
            "split": {
                "train_end": TRAIN_END,
                "val": [VAL_START, VAL_END],
                "test": [TEST_START, TEST_END],
            },
        },
        "leakage": {
            "spatial": (
                "neighbor_pm25_mean is inverse-distance PM2.5 of the 3 nearest "
                "stations at origin t; lag1/lag3 are clock lags t−1h and t−3h; "
                "spatial_gradient is own PM2.5(t) minus neighbor_pm25_mean. "
                "Neighbor PM2.5 at t+1 is not read."
            ),
            "calendar": (
                "Flags are functions of event_time_local only. "
                "is_heating_season uses documented Beijing adjustments; "
                "hours_from_cny_midnight is signed hours from 正月初一 00:00 "
                "and is null outside ±72h."
            ),
            "same_row_set": True,
            "rows": int(len(frame)),
            "null_spatial_counts": null_spatial,
            "null_hours_from_cny_midnight": null_cny_hours,
            "high_pm_and_peaks_are_post_hoc": True,
        },
        "promote_criteria_preregistered": PROMOTE_CRITERIA,
        "data": {
            "matrix": "artifacts/forecasting/feature_matrix_v2.parquet",
            "n_rows": int(len(frame)),
            "n_train": int(len(train)),
            "n_stations": int(frame["station_key"].nunique()),
            "test_cny_hours": int(
                (frame["split"].eq("test") & frame["is_chinese_new_year"].eq(1)).sum()
            ),
            "val_cny_hours": int(
                (frame["split"].eq("val") & frame["is_chinese_new_year"].eq(1)).sum()
            ),
        },
        "metrics": metrics,
        "stations_test": {
            "n_improved": improved,
            "n_stations": int(len(stations_df)),
        },
        "decisions": decisions,
    }

    pred_path = OUT / "predictions_m0_m3.parquet"
    keep_cols = [
        "station_key",
        "station_name",
        "event_time_local",
        "target_time_local",
        "split",
        "season",
        "pm25_ug_m3",
        TARGET_COL,
        "winter",
        "heating_statutory",
        "heating_adjusted",
        "rapid_rise",
        "episode_peak",
        "is_chinese_new_year",
    ]
    for name in MODELS:
        keep_cols.extend([f"y_hat_{name}", f"abs_err_{name}", f"signed_{name}"])
    eval_df.loc[:, keep_cols].to_parquet(pred_path, index=False)
    stations_df.to_csv(OUT / "delta_mae_by_station_test.csv", index=False)
    report_path = OUT / "ablation_report.json"
    report_path.write_text(
        json.dumps(report, indent=2, allow_nan=True) + "\n",
        encoding="utf-8",
    )
    summary = {
        "decisions": {k: v["decision"] for k, v in decisions.items()},
        "delta_mae_test": {
            name: metrics["overall"]["test"]["delta_mae"][name] for name in ("m1", "m2", "m3")
        },
        "delta_mae_winter_test": {
            name: metrics["winter"]["test"]["delta_mae"][name] for name in ("m1", "m2", "m3")
        },
        "delta_mae_high_pm_test": {
            name: metrics["high_pm"]["test"]["delta_mae"][name] for name in ("m1", "m2", "m3")
        },
        "delta_mae_rapid_rise_test": {
            name: metrics["rapid_rise"]["test"]["delta_mae"][name] for name in ("m1", "m2", "m3")
        },
        "m0_test_mae": metrics["overall"]["test"]["m0"]["mae"],
        "m0_winter_test_mae": metrics["winter"]["test"]["m0"]["mae"],
        "report": str(report_path.relative_to(ROOT)).replace("\\", "/"),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
