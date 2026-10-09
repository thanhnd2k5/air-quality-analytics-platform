#!/usr/bin/env python3
"""Phase 10c: persistence + Linear + HistGB → metrics + model_lock.

Example:
    py -3 scripts/run_forecasting_phase10c.py
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
    FEATURE_COLS,
    ML_END,
    ML_START,
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
    run_histgb,
    run_linear,
    run_persistence,
)

OUT = ROOT / "artifacts" / "forecasting"
MODELS = ROOT / "models" / "pm25_forecast"
MATRIX_PARQUET = OUT / "feature_matrix.parquet"
MATRIX_CSV = OUT / "feature_matrix.csv"


def _load_matrix() -> pd.DataFrame:
    if MATRIX_PARQUET.exists():
        return pd.read_parquet(MATRIX_PARQUET)
    if MATRIX_CSV.exists():
        df = pd.read_csv(MATRIX_CSV)
        df["event_time_local"] = pd.to_datetime(df["event_time_local"])
        df["target_time_local"] = pd.to_datetime(df["target_time_local"])
        return df
    raise FileNotFoundError(
        "Missing feature_matrix.parquet/csv — run scripts/run_forecasting_phase10b.py first."
    )


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    MODELS.mkdir(parents=True, exist_ok=True)

    try:
        df = _load_matrix()
        train = df[df["split"] == "train"].copy()
        if train.empty:
            raise ValueError("Empty train split")

        results = [
            run_persistence(df),
            run_linear(train, df),
            run_histgb(train, df),
        ]
        locked = choose_lock(results)
        persistence = next(r for r in results if r.name == "persistence")

        rows = []
        for r in results:
            for split, m in r.metrics.items():
                rows.append(format_metrics_row(r.name, split, m))
        metrics_df = pd.DataFrame(rows).sort_values(["model", "split"])
        metrics_path = OUT / "model_metrics.csv"
        metrics_df.to_csv(metrics_path, index=False)

        # Predictions artifact for locked model (all splits) — feeds P10d/P10e
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
        pred_path = OUT / "predictions_locked.parquet"
        try:
            pred_frame.to_parquet(pred_path, index=False)
            pred_rel = str(pred_path.relative_to(ROOT)).replace("\\", "/")
        except Exception:  # noqa: BLE001
            pred_path = OUT / "predictions_locked.csv"
            pred_frame.to_csv(pred_path, index=False)
            pred_rel = str(pred_path.relative_to(ROOT)).replace("\\", "/")

        val_mae = {r.name: r.metrics["val"]["mae"] for r in results}
        test_mae = {r.name: r.metrics["test"]["mae"] for r in results}
        beats_baseline_test = test_mae[locked.name] < test_mae["persistence"]

        model_path = MODELS / "model.joblib"
        meta_path = MODELS / "metadata.json"
        joblib.dump(
            {
                "estimator": locked.estimator,
                "feature_cols": list(FEATURE_COLS),
                "target_col": TARGET_COL,
                "model_name": locked.name,
            },
            model_path,
        )

        created_at = datetime.now(timezone.utc).isoformat()
        metadata = {
            "model_name": locked.name,
            "target": TARGET_COL,
            "horizon": "t+1h",
            "feature_cols": list(FEATURE_COLS),
            "training_period": {"start": ML_START, "end": TRAIN_END},
            "val_period": {"start": VAL_START, "end": VAL_END},
            "test_period": {"start": TEST_START, "end": TEST_END},
            "ml_window": {"start": ML_START, "end": ML_END},
            "metrics": locked.metrics,
            "random_state": RANDOM_STATE,
            "created_at": created_at,
            "dataset": "artifacts/forecasting/feature_matrix.parquet",
        }
        meta_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

        lock = {
            "ok": True,
            "phase": "P10c",
            "locked_model": locked.name,
            "lock_rule": "min val MAE among ML models (exclude persistence)",
            "random_state": RANDOM_STATE,
            "beats_persistence_on_test": beats_baseline_test,
            "val_mae": val_mae,
            "test_mae": test_mae,
            "metrics_table": str(metrics_path.relative_to(ROOT)).replace("\\", "/"),
            "predictions": pred_rel,
            "model_artifact": str(model_path.relative_to(ROOT)).replace("\\", "/"),
            "metadata": str(meta_path.relative_to(ROOT)).replace("\\", "/"),
            "split": {
                "train": {"start": ML_START, "end": TRAIN_END},
                "val": {"start": VAL_START, "end": VAL_END},
                "test": {"start": TEST_START, "end": TEST_END},
            },
            "feature_cols": list(FEATURE_COLS),
            "target_col": TARGET_COL,
            "per_model_metrics": {r.name: r.metrics for r in results},
            "created_at": created_at,
        }
        lock_path = OUT / "model_lock.json"
        lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")

        print(
            json.dumps(
                {
                    "ok": True,
                    "locked_model": locked.name,
                    "val_mae": val_mae,
                    "test_mae": test_mae,
                    "beats_persistence_on_test": beats_baseline_test,
                    "lock": str(lock_path),
                    "metrics": str(metrics_path),
                },
                ensure_ascii=False,
            )
        )
        return 0
    except Exception as exc:  # noqa: BLE001
        report = {"ok": False, "phase": "P10c", "error": str(exc)}
        path = OUT / "model_lock.json"
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"output": str(path), **report}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
