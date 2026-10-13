"""Sequence builder for LSTM experiment (from feature_matrix_v2)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from src.forecasting.constants import (
    LSTM_SEQ_COLS,
    LSTM_SEQ_LEN,
    TARGET_COL,
)


@dataclass
class LstmSequences:
    """Aligned sequence tensors + metadata for train/val/test."""

    X: np.ndarray  # (n, seq_len, n_features)
    station_ids: np.ndarray  # (n,) int64 — embedding indices
    y: np.ndarray  # (n,)
    meta: pd.DataFrame
    station_to_id: dict[int, int]
    feature_cols: tuple[str, ...]
    seq_len: int


def _require_cols(df: pd.DataFrame, cols: Sequence[str]) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for LSTM sequences: {missing}")


def build_station_id_map(station_keys: Sequence[int]) -> dict[int, int]:
    """Stable 0..K-1 map sorted by station_key (train vocabulary)."""
    keys = sorted({int(k) for k in station_keys})
    return {k: i for i, k in enumerate(keys)}


def build_sequences(
    df: pd.DataFrame,
    *,
    seq_cols: Sequence[str] = LSTM_SEQ_COLS,
    seq_len: int = LSTM_SEQ_LEN,
    station_to_id: dict[int, int] | None = None,
) -> LstmSequences:
    """Build causal windows ending at origin t (no future features).

    For each station, rows sorted by event_time_local. A sample at row i is valid
    when the previous ``seq_len`` hours (including i) are contiguous (1h gaps)
    and ``y_pm25_tplus1`` is non-null. Features are taken only from [i-seq_len+1, i].
    """
    _require_cols(
        df,
        list(seq_cols)
        + [
            "station_key",
            "event_time_local",
            "target_time_local",
            "split",
            TARGET_COL,
            "pm25_ug_m3",
            "cluster_id",
            "cluster_label",
            "season",
            "hour",
        ],
    )
    work = df.copy()
    work["event_time_local"] = pd.to_datetime(work["event_time_local"])
    work["target_time_local"] = pd.to_datetime(work["target_time_local"])

    if station_to_id is None:
        station_to_id = build_station_id_map(work["station_key"].tolist())

    xs: list[np.ndarray] = []
    ys: list[float] = []
    sids: list[int] = []
    meta_rows: list[dict] = []

    feat_list = list(seq_cols)
    for station_key, sub in work.groupby("station_key", sort=True):
        sk = int(station_key)
        if sk not in station_to_id:
            continue
        sub = sub.sort_values("event_time_local").reset_index(drop=True)
        if len(sub) < seq_len:
            continue
        times = sub["event_time_local"].to_numpy()
        feats = sub.loc[:, feat_list].to_numpy(dtype=np.float64)
        targets = sub[TARGET_COL].to_numpy(dtype=np.float64)
        sid = station_to_id[sk]

        for i in range(seq_len - 1, len(sub)):
            if not np.isfinite(targets[i]):
                continue
            window_times = times[i - seq_len + 1 : i + 1]
            gaps = np.diff(window_times) / np.timedelta64(1, "h")
            if not np.allclose(gaps, 1.0):
                continue
            xs.append(feats[i - seq_len + 1 : i + 1])
            ys.append(float(targets[i]))
            sids.append(sid)
            row = sub.iloc[i]
            meta_rows.append(
                {
                    "station_key": sk,
                    "event_time_local": row["event_time_local"],
                    "target_time_local": row["target_time_local"],
                    "split": row["split"],
                    "pm25_ug_m3": float(row["pm25_ug_m3"]),
                    TARGET_COL: float(targets[i]),
                    "cluster_id": int(row["cluster_id"]),
                    "cluster_label": row["cluster_label"],
                    "season": row["season"],
                    "hour": int(row["hour"]),
                }
            )

    if not xs:
        raise ValueError("No valid LSTM sequences built from matrix")

    meta = pd.DataFrame(meta_rows)
    return LstmSequences(
        X=np.stack(xs, axis=0),
        station_ids=np.asarray(sids, dtype=np.int64),
        y=np.asarray(ys, dtype=np.float64),
        meta=meta,
        station_to_id=station_to_id,
        feature_cols=tuple(feat_list),
        seq_len=seq_len,
    )


def fit_scaler_on_train(
    seq: LstmSequences,
    *,
    train_mask: np.ndarray | None = None,
) -> StandardScaler:
    """Fit StandardScaler on train-origin sequence timesteps only."""
    if train_mask is None:
        train_mask = (seq.meta["split"] == "train").to_numpy()
    if not train_mask.any():
        raise ValueError("Empty train mask for scaler fit")
    flat = seq.X[train_mask].reshape(-1, seq.X.shape[-1])
    scaler = StandardScaler()
    scaler.fit(flat)
    return scaler


def transform_sequences(seq: LstmSequences, scaler: StandardScaler) -> np.ndarray:
    """Apply scaler to all sequence timesteps; returns float32 array."""
    n, t, f = seq.X.shape
    flat = seq.X.reshape(-1, f)
    scaled = scaler.transform(flat).astype(np.float32)
    return scaled.reshape(n, t, f)


def split_masks(meta: pd.DataFrame) -> dict[str, np.ndarray]:
    return {
        "train": (meta["split"] == "train").to_numpy(),
        "val": (meta["split"] == "val").to_numpy(),
        "test": (meta["split"] == "test").to_numpy(),
    }
