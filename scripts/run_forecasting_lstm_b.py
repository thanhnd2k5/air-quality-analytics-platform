#!/usr/bin/env python3
"""Vòng B LSTM experiment: train + metrics vs HistGB v2 (no production overwrite).

Example:
    py -3 scripts/run_forecasting_lstm_b.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from src.forecasting.constants import (  # noqa: E402
    LSTM_DROPOUT,
    LSTM_HIDDEN,
    LSTM_SEQ_COLS,
    LSTM_SEQ_LEN,
    LSTM_STATION_EMB_DIM,
    ML_END,
    ML_START,
    TARGET_COL,
    TEST_END,
    TEST_START,
    TRAIN_END,
    VAL_END,
    VAL_START,
)
from src.forecasting.lstm_data import (  # noqa: E402
    build_sequences,
    build_station_id_map,
    fit_scaler_on_train,
    transform_sequences,
)
from src.forecasting.lstm_model import resolve_device, train_lstm  # noqa: E402
from src.forecasting.metrics import format_metrics_row, regression_metrics  # noqa: E402
from src.forecasting.models import RANDOM_STATE  # noqa: E402

OUT = ROOT / "artifacts" / "forecasting"
MODELS = ROOT / "models" / "pm25_forecast_lstm_exp"
MATRIX_PARQUET = OUT / "feature_matrix_v2.parquet"
MATRIX_CSV = OUT / "feature_matrix_v2.csv"
V2_LOCK = OUT / "model_lock.json"  # production = HistGB v2 after promote


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


def _load_prod_lock() -> dict:
    if not V2_LOCK.is_file():
        return {}
    return json.loads(V2_LOCK.read_text(encoding="utf-8"))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    MODELS.mkdir(parents=True, exist_ok=True)

    try:
        df = _load_matrix()
        missing = [c for c in LSTM_SEQ_COLS if c not in df.columns]
        if missing:
            raise KeyError(f"Matrix missing LSTM_SEQ_COLS: {missing}")

        station_to_id = build_station_id_map(
            df.loc[df["split"] == "train", "station_key"].tolist()
        )
        seq = build_sequences(df, station_to_id=station_to_id)
        scaler = fit_scaler_on_train(seq)
        X = transform_sequences(seq, scaler)

        device = resolve_device(prefer_cuda=True)
        result = train_lstm(
            X,
            seq.station_ids,
            seq.y,
            seq.meta,
            n_stations=len(station_to_id),
            device=device,
        )

        # Persistence on the same sequence rows (origin pm25)
        y_hat_pers = seq.meta["pm25_ug_m3"].to_numpy(dtype=float)
        pers_metrics = {}
        for split in ("train", "val", "test"):
            m = (seq.meta["split"] == split).to_numpy()
            if m.any():
                pers_metrics[split] = regression_metrics(seq.y[m], y_hat_pers[m])

        rows = []
        for name, metrics in (
            ("persistence", pers_metrics),
            ("lstm", result.metrics),
        ):
            for split, m in metrics.items():
                rows.append(format_metrics_row(name, split, m))
        metrics_df = pd.DataFrame(rows).sort_values(["model", "split"])
        metrics_path = OUT / "lstm_exp_metrics.csv"
        metrics_df.to_csv(metrics_path, index=False)

        pred_frame = seq.meta.copy()
        pred_frame["y_hat_persistence"] = y_hat_pers
        pred_frame["y_hat_locked"] = result.predictions
        pred_frame["abs_error_locked"] = (
            pred_frame[TARGET_COL] - pred_frame["y_hat_locked"]
        ).abs()
        pred_path = OUT / "lstm_exp_predictions.parquet"
        try:
            pred_frame.to_parquet(pred_path, index=False)
            pred_rel = str(pred_path.relative_to(ROOT)).replace("\\", "/")
        except Exception:  # noqa: BLE001
            pred_path = OUT / "lstm_exp_predictions.csv"
            pred_frame.to_csv(pred_path, index=False)
            pred_rel = str(pred_path.relative_to(ROOT)).replace("\\", "/")

        prod = _load_prod_lock()
        histgb_test = float(
            prod.get("test_mae", {}).get("hist_gradient_boosting", float("nan"))
        )
        histgb_val = float(
            prod.get("val_mae", {}).get("hist_gradient_boosting", float("nan"))
        )
        lstm_test = result.metrics["test"]["mae"]
        lstm_val = result.metrics["val"]["mae"]
        pers_test = pers_metrics["test"]["mae"]

        comparison = {
            "persistence_test_mae": pers_test,
            "histgb_v2_prod_test_mae": histgb_test,
            "histgb_v2_prod_val_mae": histgb_val,
            "lstm_test_mae": lstm_test,
            "lstm_val_mae": lstm_val,
            "lift_vs_persistence_test": pers_test - lstm_test,
            "delta_vs_histgb_v2_test_mae": lstm_test - histgb_test
            if histgb_test == histgb_test
            else None,
            "beats_persistence_on_test": lstm_test < pers_test,
            "beats_histgb_v2_on_test": (
                lstm_test < histgb_test if histgb_test == histgb_test else None
            ),
            "n_sequences": {
                "train": int((seq.meta["split"] == "train").sum()),
                "val": int((seq.meta["split"] == "val").sum()),
                "test": int((seq.meta["split"] == "test").sum()),
            },
            "note": "LSTM sequences require 24h history — n may be slightly under flat matrix",
        }
        comparison_path = OUT / "lstm_exp_comparison.json"
        comparison_path.write_text(
            json.dumps(comparison, indent=2) + "\n", encoding="utf-8"
        )

        model_path = MODELS / "model.pt"
        scaler_path = MODELS / "scaler.joblib"
        meta_path = MODELS / "metadata.json"
        torch.save(
            {
                "state_dict": result.model.state_dict(),
                "n_features": X.shape[-1],
                "n_stations": len(station_to_id),
                "station_to_id": station_to_id,
                "hidden": LSTM_HIDDEN,
                "dropout": LSTM_DROPOUT,
                "emb_dim": LSTM_STATION_EMB_DIM,
                "seq_len": LSTM_SEQ_LEN,
                "feature_cols": list(LSTM_SEQ_COLS),
            },
            model_path,
        )
        joblib.dump(scaler, scaler_path)

        created_at = datetime.now(timezone.utc).isoformat()
        metadata = {
            "model_name": "lstm",
            "variant": "lstm_exp",
            "target": TARGET_COL,
            "horizon": "t+1h",
            "seq_len": LSTM_SEQ_LEN,
            "feature_cols": list(LSTM_SEQ_COLS),
            "hidden": LSTM_HIDDEN,
            "dropout": LSTM_DROPOUT,
            "station_emb_dim": LSTM_STATION_EMB_DIM,
            "training_period": {"start": ML_START, "end": TRAIN_END},
            "val_period": {"start": VAL_START, "end": VAL_END},
            "test_period": {"start": TEST_START, "end": TEST_END},
            "ml_window": {"start": ML_START, "end": ML_END},
            "metrics": result.metrics,
            "best_epoch": result.best_epoch,
            "history": result.history,
            "device": result.device,
            "random_state": RANDOM_STATE,
            "created_at": created_at,
            "dataset": "artifacts/forecasting/feature_matrix_v2.parquet",
            "note": "Experiment only — does not replace production model_lock.json",
        }
        meta_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

        lock = {
            "ok": True,
            "phase": "VongB_LSTM",
            "variant": "lstm_exp",
            "locked_model": "lstm",
            "lock_rule": "early_stop_val_mae patience=5 max_epochs=30",
            "random_state": RANDOM_STATE,
            "best_epoch": result.best_epoch,
            "device": result.device,
            "beats_persistence_on_test": comparison["beats_persistence_on_test"],
            "beats_histgb_v2_on_test": comparison["beats_histgb_v2_on_test"],
            "val_mae": {
                "persistence": pers_metrics["val"]["mae"],
                "lstm": lstm_val,
            },
            "test_mae": {
                "persistence": pers_test,
                "lstm": lstm_test,
            },
            "comparison_vs_histgb_v2": comparison,
            "metrics_table": str(metrics_path.relative_to(ROOT)).replace("\\", "/"),
            "predictions": pred_rel,
            "model_artifact": str(model_path.relative_to(ROOT)).replace("\\", "/"),
            "scaler_artifact": str(scaler_path.relative_to(ROOT)).replace("\\", "/"),
            "metadata": str(meta_path.relative_to(ROOT)).replace("\\", "/"),
            "split": {
                "train": {"start": ML_START, "end": TRAIN_END},
                "val": {"start": VAL_START, "end": VAL_END},
                "test": {"start": TEST_START, "end": TEST_END},
            },
            "feature_cols": list(LSTM_SEQ_COLS),
            "seq_len": LSTM_SEQ_LEN,
            "target_col": TARGET_COL,
            "created_at": created_at,
            "note": "Experimental lock only — production remains artifacts/forecasting/model_lock.json",
        }
        lock_path = OUT / "lstm_exp_lock.json"
        lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")

        print(
            json.dumps(
                {
                    "ok": True,
                    "device": result.device,
                    "best_epoch": result.best_epoch,
                    "val_mae": lock["val_mae"],
                    "test_mae": lock["test_mae"],
                    "comparison_vs_histgb_v2": comparison,
                    "lock": str(lock_path),
                    "metrics": str(metrics_path),
                },
                ensure_ascii=True,
            )
        )
        return 0
    except Exception as exc:  # noqa: BLE001
        report = {"ok": False, "phase": "VongB_LSTM", "error": str(exc)}
        path = OUT / "lstm_exp_lock.json"
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"output": str(path), **report}, ensure_ascii=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
