"""Train/validation reliability check for the locked PM2.5 forecast.

Drops every held-out row before spatial features are built and before any
score is computed. Does not fit a model and does not rewrite a prediction.
The keep/close rule lives in src/forecasting/reliability.py.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.forecasting.constants import TARGET_COL  # noqa: E402
from src.forecasting.reliability import (  # noqa: E402
    CANDIDATE_FLAGS,
    PRIMARY_ERROR_UG,
    REFERENCE_FLAGS,
    SENSITIVITY_ERROR_UG,
    add_visible_flags,
    assert_confirmation_frame,
    decide,
    score_flag,
)
from src.forecasting.spatial_calendar import add_spatial_features  # noqa: E402
from src.forecasting.spatial_quality import score_spatial_quality  # noqa: E402

MATRIX = ROOT / "artifacts" / "forecasting" / "feature_matrix_v2.parquet"
PREDICTIONS = ROOT / "artifacts" / "forecasting" / "predictions_locked.parquet"
STATIONS = ROOT / "data" / "raw" / "reference" / "stations.csv"
STATION_MAP = ROOT / "data" / "clustering" / "station_cluster_assignment.csv"
OUT = ROOT / "artifacts" / "forecasting" / "reliability"
FLAG_COLUMNS = CANDIDATE_FLAGS + REFERENCE_FLAGS


def _jsonable(value):
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if np.isfinite(number) else None
    return value


def _load_confirmation_frame() -> pd.DataFrame:
    matrix = pd.read_parquet(
        MATRIX,
        columns=[
            "station_key",
            "event_time_local",
            "split",
            "pm25_ug_m3",
            "pm25_delta_1",
            "in_episode_flag",
            "pm10_ug_m3",
            "co_ug_m3",
            TARGET_COL,
        ],
    )
    predictions = pd.read_parquet(
        PREDICTIONS,
        columns=[
            "station_key",
            "event_time_local",
            "split",
            "y_hat_locked",
            "abs_error_locked",
            TARGET_COL,
        ],
    )
    matrix = matrix[matrix["split"].isin(["train", "val"])].copy()
    predictions = predictions[predictions["split"].isin(["train", "val"])].copy()
    assert_confirmation_frame(matrix)
    assert_confirmation_frame(predictions)
    matrix["event_time_local"] = pd.to_datetime(matrix["event_time_local"])
    predictions["event_time_local"] = pd.to_datetime(predictions["event_time_local"])
    matrix["station_key"] = matrix["station_key"].astype(int)
    predictions["station_key"] = predictions["station_key"].astype(int)
    frame = matrix.merge(
        predictions,
        on=["station_key", "event_time_local", "split", TARGET_COL],
        how="inner",
        validate="one_to_one",
    )
    if len(frame) != len(matrix):
        raise ValueError("locked predictions do not match the confirmation rows of the feature matrix")
    reconstructed = (frame[TARGET_COL] - frame["y_hat_locked"]).abs()
    if not np.allclose(reconstructed, frame["abs_error_locked"], equal_nan=False):
        raise ValueError("abs_error_locked does not match |target - locked prediction|")
    names = pd.read_csv(STATION_MAP)[["station_key", "station_name"]]
    names["station_key"] = names["station_key"].astype(int)
    frame = frame.merge(names, on="station_key", how="left")
    if frame["station_name"].isna().any():
        raise KeyError("station_key missing from cluster assignment")
    return frame


def _attach_visible_context(frame: pd.DataFrame) -> pd.DataFrame:
    stations = pd.read_csv(STATIONS)
    with_space, _neighbors = add_spatial_features(frame, stations, include_median=True)
    panel = with_space.loc[
        :,
        ["station_name", "event_time_local", "pm25_ug_m3", "pm10_ug_m3", "co_ug_m3"],
    ].copy()
    scored = score_spatial_quality(panel, stations)
    causal = scored.loc[:, ["station_name", "event_time_local", "suspect_spatiotemporal_causal"]]
    merged = with_space.merge(causal, on=["station_name", "event_time_local"], how="left", validate="one_to_one")
    if merged["suspect_spatiotemporal_causal"].isna().any():
        raise ValueError("causal suspect flag missing after the spatial-quality join")
    return add_visible_flags(merged)


def _score_table(frame: pd.DataFrame) -> list[dict]:
    rows: list[dict] = []
    for split, part in frame.groupby("split", sort=False):
        error = part["abs_error_locked"].to_numpy(dtype=float)
        for outcome, cut in (("primary", PRIMARY_ERROR_UG), ("sensitivity", SENSITIVITY_ERROR_UG)):
            for flag in FLAG_COLUMNS:
                score = score_flag(error, part[flag].to_numpy(dtype=bool), cut=cut)
                rows.append({"split": str(split), "flag": flag, "outcome": outcome, "error_cut": cut, **score})
    return rows


def main() -> None:
    frame = _attach_visible_context(_load_confirmation_frame())
    assert_confirmation_frame(frame)
    if set(frame["split"].astype(str)) != {"train", "val"}:
        raise ValueError("confirmation frame must contain both train and validation")
    scores = _score_table(frame)
    decision = decide(scores)
    report = {
        "predictions": "artifacts/forecasting/predictions_locked.parquet",
        "feature_matrix": "artifacts/forecasting/feature_matrix_v2.parquet",
        "test_rows_scored": 0,
        "n_by_split": {split: int(n) for split, n in frame.groupby("split").size().items()},
        "primary_error_ug": PRIMARY_ERROR_UG,
        "sensitivity_error_ug": SENSITIVITY_ERROR_UG,
        "sensitivity_changes_decision": False,
        "bar": {
            "min_flagged": 30,
            "max_flag_rate": 0.20,
            "min_recall": 0.25,
            "min_precision_lift": 2.0,
            "both_splits": True,
        },
        **decision,
        "scores": scores,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    table = pd.DataFrame(scores)
    table.to_csv(OUT / "signal_scores.csv", index=False)
    (OUT / "reliability_report.json").write_text(json.dumps(_jsonable(report), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_jsonable({**decision, "n_by_split": report["n_by_split"]}), indent=2))


if __name__ == "__main__":
    main()
