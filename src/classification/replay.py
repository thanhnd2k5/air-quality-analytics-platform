"""Historical replay: issue an alert at the watermark, score it only later.

The local files already contain the whole record. This walk still hides the
next hour until the watermark reaches it. ``suspect_spatiotemporal`` uses the
next hour, so it is attached only when that hour is scored, never as a
feature.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

import numpy as np
import pandas as pd

from src.classification.constants import ALERT_THRESHOLD

BANNED_FEATURE_MARKERS = ("suspect", "y_true", "y_pm25_tplus", "y_alert", "y_pm25_target")


def assert_feature_names(columns: Sequence[str]) -> None:
    banned = [name for name in columns if any(marker in name.lower() for marker in BANNED_FEATURE_MARKERS)]
    if banned:
        raise RuntimeError(f"Replay features include future or review columns: {banned}")


def _as_timestamp(value: Any) -> pd.Timestamp:
    return pd.Timestamp(value)


def _batch_ends(start: pd.Timestamp, end: pd.Timestamp, batch_hours: int) -> list[pd.Timestamp]:
    if batch_hours < 1:
        raise ValueError("batch_hours must be ≥ 1")
    if end < start:
        raise ValueError("replay end is before start")
    ends: list[pd.Timestamp] = []
    cursor = start + pd.Timedelta(hours=batch_hours - 1)
    while cursor < end:
        ends.append(cursor)
        cursor = cursor + pd.Timedelta(hours=batch_hours)
    ends.append(end)
    return ends


def _confusion(y_true: np.ndarray, pred: np.ndarray) -> dict[str, float | int | None]:
    if len(y_true) == 0:
        return {"n": 0, "tp": 0, "fp": 0, "fn": 0, "tn": 0, "f1": None}
    yt = y_true.astype(int)
    yp = pred.astype(int)
    tp = int(((yt == 1) & (yp == 1)).sum())
    fp = int(((yt == 0) & (yp == 1)).sum())
    fn = int(((yt == 1) & (yp == 0)).sum())
    tn = int(((yt == 0) & (yp == 0)).sum())
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and (precision + recall) > 0
        else None
    )
    return {"n": int(len(yt)), "tp": tp, "fp": fp, "fn": fn, "tn": tn, "f1": f1}


def view_at(rows: Sequence[dict[str, Any]], watermark: str) -> list[dict[str, Any]]:
    """Rows issued by this watermark, with the next hour hidden until it arrives."""
    limit = _as_timestamp(watermark)
    visible: list[dict[str, Any]] = []
    for row in rows:
        if _as_timestamp(row["issued_watermark"]) > limit:
            continue
        shown = dict(row)
        scored_at = row["scored_watermark"]
        if scored_at is None or _as_timestamp(scored_at) > limit:
            shown["y_true"] = None
            shown["suspect_spatiotemporal"] = None
            shown["status"] = "waiting"
        else:
            shown["status"] = "scored"
        visible.append(shown)
    return visible


def replay_alerts(
    origins: pd.DataFrame,
    predict: Callable[[pd.DataFrame], np.ndarray],
    *,
    start: str,
    end: str,
    batch_hours: int,
    model_version: str,
    cutoff: float,
    actual_col: str = "y_true_hidden",
    feature_cols: Sequence[str],
    suspect: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Walk ``start``..``end`` in batches. ``predict`` sees only the open batch."""
    assert_feature_names(feature_cols)
    if actual_col in feature_cols:
        raise RuntimeError("The hidden actual column is not a feature")
    frame = origins.copy()
    frame["event_time_local"] = pd.to_datetime(frame["event_time_local"])
    start_ts = _as_timestamp(start)
    end_ts = _as_timestamp(end)
    window = frame[
        (frame["event_time_local"] >= start_ts) & (frame["event_time_local"] <= end_ts)
    ].copy()
    origin_times = pd.to_datetime(window["event_time_local"])
    actual_keys = list(zip(window["station_key"].astype(int), origin_times + pd.Timedelta(hours=1)))
    actuals = dict(zip(actual_keys, window[actual_col].tolist()))

    suspect_map: dict[tuple[int, pd.Timestamp], bool] = {}
    if suspect is not None and not suspect.empty:
        for record in suspect.itertuples(index=False):
            suspect_map[(int(record.station_key), pd.Timestamp(record.event_time_local))] = bool(
                record.suspect_spatiotemporal
            )

    issued: list[dict[str, Any]] = []
    batches: list[dict[str, Any]] = []
    previous = start_ts - pd.Timedelta(hours=1)
    for watermark in _batch_ends(start_ts, end_ts, batch_hours):
        batch = window[
            (window["event_time_local"] > previous) & (window["event_time_local"] <= watermark)
        ].sort_values(["event_time_local", "station_key"])
        if batch["event_time_local"].max() > watermark if len(batch) else False:
            raise RuntimeError("A batch origin is after its watermark")
        probabilities = np.zeros(0, dtype=float)
        if len(batch):
            features = batch.loc[:, list(feature_cols)]
            assert_feature_names(features.columns)
            probabilities = np.asarray(predict(features), dtype=float)
            if len(probabilities) != len(batch):
                raise RuntimeError("predict() length does not match the batch")
        new_rows: list[dict[str, Any]] = []
        for offset, record in enumerate(batch.itertuples(index=False)):
            origin = pd.Timestamp(record.event_time_local)
            probability = float(probabilities[offset])
            new_rows.append(
                {
                    "station_key": int(record.station_key),
                    "station_name": str(record.station_name),
                    "origin_time": origin.strftime("%Y-%m-%d %H:%M:%S"),
                    "target_time": (origin + pd.Timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
                    "issued_watermark": watermark.strftime("%Y-%m-%d %H:%M:%S"),
                    "model_version": model_version,
                    "probability": probability,
                    "alert": bool(probability >= cutoff),
                    "persistence_alert": bool(float(record.pm25_ug_m3) >= ALERT_THRESHOLD),
                    "origin_pm25": float(record.pm25_ug_m3),
                    "origin_pm10": None if pd.isna(getattr(record, "pm10_ug_m3", np.nan)) else float(record.pm10_ug_m3),
                    "origin_co": None if pd.isna(getattr(record, "co_ug_m3", np.nan)) else float(record.co_ug_m3),
                    "source_file": f"data/raw/uci/PRSA_Data_{record.station_name}_20130301-20170228.csv",
                    "y_true": None,
                    "suspect_spatiotemporal": None,
                    "scored_watermark": None,
                }
            )
        for row in issued:
            target = _as_timestamp(row["target_time"])
            if row["scored_watermark"] is not None or target > watermark:
                continue
            key = (int(row["station_key"]), target)
            if key not in actuals or pd.isna(actuals[key]):
                continue
            row["y_true"] = float(actuals[key])
            row["scored_watermark"] = watermark.strftime("%Y-%m-%d %H:%M:%S")
            row["suspect_spatiotemporal"] = suspect_map.get(key)
        for row in new_rows:
            target = _as_timestamp(row["target_time"])
            if target <= watermark and (int(row["station_key"]), target) in actuals and pd.notna(
                actuals[(int(row["station_key"]), target)]
            ):
                row["y_true"] = float(actuals[(int(row["station_key"]), target)])
                row["scored_watermark"] = watermark.strftime("%Y-%m-%d %H:%M:%S")
                row["suspect_spatiotemporal"] = suspect_map.get((int(row["station_key"]), target))
        issued.extend(new_rows)
        for row in issued:
            scored_at = row["scored_watermark"]
            if scored_at is not None and _as_timestamp(row["target_time"]) > _as_timestamp(scored_at):
                raise RuntimeError("Scored a target that the watermark had not reached")
            if row["suspect_spatiotemporal"] is not None and row["scored_watermark"] is None:
                raise RuntimeError("Review flag attached before the target hour arrived")
        scored = [row for row in issued if row["y_true"] is not None and _as_timestamp(row["scored_watermark"]) <= watermark]
        y_true = np.array([int(float(row["y_true"]) >= ALERT_THRESHOLD) for row in scored], dtype=int)
        model_pred = np.array([int(row["alert"]) for row in scored], dtype=int)
        persistence_pred = np.array([int(row["persistence_alert"]) for row in scored], dtype=int)
        waiting = sum(1 for row in issued if row["scored_watermark"] is None or _as_timestamp(row["scored_watermark"]) > watermark)
        batches.append(
            {
                "watermark": watermark.strftime("%Y-%m-%d %H:%M:%S"),
                "n_issued": len(new_rows),
                "n_alerts": int(sum(row["alert"] for row in new_rows)),
                "n_stations": int(batch["station_key"].nunique()) if len(batch) else 0,
                "n_waiting": int(waiting),
                "n_scored": len(scored),
                "model": _confusion(y_true, model_pred),
                "persistence": _confusion(y_true, persistence_pred),
            }
        )
        previous = watermark
    return {
        "label": "Phát lại dữ liệu lịch sử",
        "window": {"start": start_ts.strftime("%Y-%m-%d %H:%M:%S"), "end": end_ts.strftime("%Y-%m-%d %H:%M:%S")},
        "batch_hours": batch_hours,
        "model_version": model_version,
        "probability_cutoff": cutoff,
        "batches": batches,
        "rows": issued,
    }
