#!/usr/bin/env python3
"""Vòng A / A2: train HistGB v2 + sample weight; compare to v1 lock (no overwrite).

Example:
    py -3 scripts/run_forecasting_v2b.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from src.forecasting.constants import (  # noqa: E402
    FEATURE_COLS_V2,
    ML_END,
    ML_START,
    SAMPLE_WEIGHT_HIGH,
    SAMPLE_WEIGHT_THRESHOLD,
    TARGET_COL,
    TEST_END,
    TEST_START,
    TRAIN_END,
    VAL_END,
    VAL_START,
)
from src.forecasting.metrics import format_metrics_row  # noqa: E402
from src.forecasting.models import (  # noqa: E402
    RANDOM_STATE,
    choose_lock,
    compute_sample_weights,
    run_histgb,
    run_linear,
    run_persistence,
)

OUT = ROOT / "artifacts" / "forecasting"
MODELS = ROOT / "models" / "pm25_forecast_v2"
MATRIX_PARQUET = OUT / "feature_matrix_v2.parquet"
MATRIX_CSV = OUT / "feature_matrix_v2.csv"
V1_LOCK = OUT / "model_lock.json"


def _load_matrix() -> pd.DataFrame:
    if MATRIX_PARQUET.exists():
        return pd.read_parquet(MATRIX_PARQUET)
    if MATRIX_CSV.exists():
        df = pd.read_csv(MATRIX_CSV)
        df["event_time_local"] = pd.to_datetime(df["event_time_local"])
        df["target_time_local"] = pd.to_datetime(df["target_time_local"])
        return df
    raise FileNotFoundError(
        "Missing feature_matrix_v2 — run scripts/run_forecasting_v2a.py first."
    )


def _load_v1_lock() -> dict:
    if not V1_LOCK.is_file():
        return {}
    return json.loads(V1_LOCK.read_text(encoding="utf-8"))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    MODELS.mkdir(parents=True, exist_ok=True)

    try:
        df = _load_matrix()
        train = df[df["split"] == "train"].copy()
        if train.empty:
            raise ValueError("Empty train split")

        weights = compute_sample_weights(
            train["pm25_ug_m3"],
            train[TARGET_COL],
            threshold=SAMPLE_WEIGHT_THRESHOLD,
            high_weight=SAMPLE_WEIGHT_HIGH,
        )

        results = [
            run_persistence(df),
            run_linear(train, df, feature_cols=FEATURE_COLS_V2),
            run_histgb(
                train,
                df,
                feature_cols=FEATURE_COLS_V2,
                sample_weight=weights,
            ),
        ]
        locked = choose_lock(results)
        persistence = next(r for r in results if r.name == "persistence")

        rows = []
        for r in results:
            for split, m in r.metrics.items():
                rows.append(format_metrics_row(r.name, split, m))
        metrics_df = pd.DataFrame(rows).sort_values(["model", "split"])
        metrics_path = OUT / "model_metrics_v2.csv"
        metrics_df.to_csv(metrics_path, index=False)

        pred_frame = df[
            [
                "station_key",
                "event_time_local",
                "target_time_local",
                "split",
                "pm25_ug_m3",
                TARGET_COL,
                "cluster_id",
                "cluster_label",
                "season",
                "hour",
            ]
        ].copy()
        pred_frame["y_hat_persistence"] = persistence.predictions
        pred_frame["y_hat_locked"] = locked.predictions
        pred_frame["abs_error_locked"] = (
            pred_frame[TARGET_COL] - pred_frame["y_hat_locked"]
        ).abs()
        pred_path = OUT / "predictions_v2.parquet"
        try:
            pred_frame.to_parquet(pred_path, index=False)
            pred_rel = str(pred_path.relative_to(ROOT)).replace("\\", "/")
        except Exception:  # noqa: BLE001
            pred_path = OUT / "predictions_v2.csv"
            pred_frame.to_csv(pred_path, index=False)
            pred_rel = str(pred_path.relative_to(ROOT)).replace("\\", "/")

        val_mae = {r.name: r.metrics["val"]["mae"] for r in results}
        test_mae = {r.name: r.metrics["test"]["mae"] for r in results}
        beats_baseline_test = test_mae[locked.name] < test_mae["persistence"]

        v1 = _load_v1_lock()
        v1_test = float(v1.get("test_mae", {}).get("hist_gradient_boosting", float("nan")))
        v1_val = float(v1.get("val_mae", {}).get("hist_gradient_boosting", float("nan")))
        comparison = {
            "persistence_test_mae": test_mae["persistence"],
            "histgb_v1_lock_test_mae": v1_test,
            "histgb_v1_lock_val_mae": v1_val,
            "histgb_v2_test_mae": test_mae[locked.name],
            "histgb_v2_val_mae": val_mae[locked.name],
            "lift_vs_persistence_test": test_mae["persistence"] - test_mae[locked.name],
            "delta_vs_v1_test_mae": test_mae[locked.name] - v1_test
            if v1_test == v1_test
            else None,
            "beats_persistence_on_test": beats_baseline_test,
            "beats_v1_lock_on_test": (
                test_mae[locked.name] < v1_test if v1_test == v1_test else None
            ),
        }
        comparison_path = OUT / "model_comparison_v2.json"
        comparison_path.write_text(json.dumps(comparison, indent=2) + "\n", encoding="utf-8")

        model_path = MODELS / "model.joblib"
        meta_path = MODELS / "metadata.json"
        joblib.dump(
            {
                "estimator": locked.estimator,
                "feature_cols": list(FEATURE_COLS_V2),
                "target_col": TARGET_COL,
                "model_name": locked.name,
                "sample_weight": {
                    "threshold": SAMPLE_WEIGHT_THRESHOLD,
                    "high_weight": SAMPLE_WEIGHT_HIGH,
                },
            },
            model_path,
        )

        created_at = datetime.now(timezone.utc).isoformat()
        metadata = {
            "model_name": locked.name,
            "variant": "v2",
            "target": TARGET_COL,
            "horizon": "t+1h",
            "feature_cols": list(FEATURE_COLS_V2),
            "sample_weight": {
                "threshold": SAMPLE_WEIGHT_THRESHOLD,
                "high_weight": SAMPLE_WEIGHT_HIGH,
                "rule": "w=2 if pm25(t)>=115 or y>=115 else 1",
            },
            "training_period": {"start": ML_START, "end": TRAIN_END},
            "val_period": {"start": VAL_START, "end": VAL_END},
            "test_period": {"start": TEST_START, "end": TEST_END},
            "ml_window": {"start": ML_START, "end": ML_END},
            "metrics": locked.metrics,
            "random_state": RANDOM_STATE,
            "created_at": created_at,
            "dataset": "artifacts/forecasting/feature_matrix_v2.parquet",
            "note": "Experimental — does not replace models/pm25_forecast or model_lock.json",
        }
        meta_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

        lock = {
            "ok": True,
            "phase": "VongA_A2",
            "variant": "v2",
            "locked_model": locked.name,
            "lock_rule": "min val MAE among ML models (exclude persistence)",
            "random_state": RANDOM_STATE,
            "sample_weight": metadata["sample_weight"],
            "beats_persistence_on_test": beats_baseline_test,
            "val_mae": val_mae,
            "test_mae": test_mae,
            "comparison_vs_v1": comparison,
            "metrics_table": str(metrics_path.relative_to(ROOT)).replace("\\", "/"),
            "predictions": pred_rel,
            "model_artifact": str(model_path.relative_to(ROOT)).replace("\\", "/"),
            "metadata": str(meta_path.relative_to(ROOT)).replace("\\", "/"),
            "split": {
                "train": {"start": ML_START, "end": TRAIN_END},
                "val": {"start": VAL_START, "end": VAL_END},
                "test": {"start": TEST_START, "end": TEST_END},
            },
            "feature_cols": list(FEATURE_COLS_V2),
            "target_col": TARGET_COL,
            "per_model_metrics": {r.name: r.metrics for r in results},
            "created_at": created_at,
            "note": "Experimental lock only — production remains artifacts/forecasting/model_lock.json",
        }
        lock_path = OUT / "model_lock_v2.json"
        lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")

        print(
            json.dumps(
                {
                    "ok": True,
                    "locked_model": locked.name,
                    "val_mae": val_mae,
                    "test_mae": test_mae,
                    "comparison_vs_v1": comparison,
                    "lock": str(lock_path),
                    "metrics": str(metrics_path),
                },
                ensure_ascii=False,
            )
        )
        return 0
    except Exception as exc:  # noqa: BLE001
        report = {"ok": False, "phase": "VongA_A2", "error": str(exc)}
        path = OUT / "model_lock_v2.json"
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"output": str(path), **report}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
