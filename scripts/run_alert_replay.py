#!/usr/bin/env python3
"""Replay the locked t+1 alert across 18–21 Dec 2016 in six-hour batches.

Writes the same JSON the dashboard reads. The locked model file is not changed.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.diagnose_evaluation_hygiene import STATIONS, load_uci_hourly  # noqa: E402
from src.classification.models import feature_frame  # noqa: E402
from src.classification.replay import replay_alerts  # noqa: E402
from src.forecasting.spatial_quality import score_spatial_quality  # noqa: E402

MATRIX = ROOT / "artifacts" / "forecasting" / "feature_matrix_v2.parquet"
METADATA = ROOT / "models" / "pm25_alert" / "metadata.json"
MODEL = ROOT / "models" / "pm25_alert" / "model.joblib"
OUT = ROOT / "artifacts" / "classification" / "replay" / "replay.json"
PUBLIC = ROOT / "dashboard" / "web" / "public" / "replay" / "replay.json"
START = "2016-12-18 00:00:00"
END = "2016-12-21 23:00:00"


def main() -> None:
    metadata = json.loads(METADATA.read_text(encoding="utf-8"))
    feature_cols = list(metadata["feature_cols"])
    blob = joblib.load(MODEL)
    estimator = blob["estimator"] if isinstance(blob, dict) else blob
    model_version = f"{metadata['model_name']}@{metadata['probability_cutoff']}"

    matrix = pd.read_parquet(MATRIX)
    stations = pd.read_csv(STATIONS)
    if "station_name" not in matrix.columns:
        names = stations.rename(columns={"station_id": "station_key"})[["station_key", "station_name"]]
        matrix = matrix.merge(names, on="station_key", how="left")
    matrix["event_time_local"] = pd.to_datetime(matrix["event_time_local"])
    window = matrix[
        (matrix["event_time_local"] >= START) & (matrix["event_time_local"] <= END)
    ].copy()
    window["y_true_hidden"] = window["y_pm25_tplus1"]

    hourly = load_uci_hourly()
    hourly["event_time_local"] = pd.to_datetime(hourly["event_time_local"])
    panel = hourly[
        (hourly["event_time_local"] >= "2016-12-17 00:00:00")
        & (hourly["event_time_local"] <= "2016-12-22 23:00:00")
    ][["station_name", "event_time_local", "pm25_ug_m3", "station_key"]]
    scored = score_spatial_quality(panel, stations)
    suspect = scored[["station_key", "event_time_local", "suspect_spatiotemporal"]]

    def predict(features: pd.DataFrame):
        frame = feature_frame(features, feature_cols)
        return estimator.predict_proba(frame)[:, 1]

    payload = replay_alerts(
        window,
        predict,
        start=START,
        end=END,
        batch_hours=6,
        model_version=model_version,
        cutoff=float(metadata["probability_cutoff"]),
        feature_cols=feature_cols,
        suspect=suspect,
    )
    payload["task"] = metadata["task"]
    payload["source_matrix"] = "artifacts/forecasting/feature_matrix_v2.parquet"
    payload["model_path"] = "models/pm25_alert/model.joblib"
    text = json.dumps(payload, indent=2)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    PUBLIC.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(OUT, PUBLIC)
    print(
        f"batches={len(payload['batches'])} rows={len(payload['rows'])} -> {OUT}",
        flush=True,
    )


if __name__ == "__main__":
    main()
