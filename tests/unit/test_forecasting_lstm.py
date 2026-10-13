"""Unit tests for LSTM sequence builder / model (no GPU required)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import torch

from src.forecasting.constants import LSTM_SEQ_COLS, LSTM_SEQ_LEN, TARGET_COL
from src.forecasting.lstm_data import (
    build_sequences,
    build_station_id_map,
    fit_scaler_on_train,
    transform_sequences,
)
from src.forecasting.lstm_model import Pm25LSTM


def _toy_matrix(
    *,
    n_hours: int = 40,
    station_keys: tuple[int, ...] = (1, 2),
    start: str = "2015-01-01 00:00:00",
) -> pd.DataFrame:
    rows = []
    for sk in station_keys:
        times = pd.date_range(start, periods=n_hours, freq="h")
        for i, t in enumerate(times):
            pm = float(10 + sk + i)
            split = "train" if t.year <= 2015 else "val"
            rows.append(
                {
                    "station_key": sk,
                    "event_time_local": t,
                    "target_time_local": t + pd.Timedelta(hours=1),
                    "split": split,
                    "pm25_ug_m3": pm,
                    TARGET_COL: pm + 1.0 if i < n_hours - 1 else np.nan,
                    "temperature_c": 10.0,
                    "relative_humidity_pct": 50.0,
                    "wind_speed_m_s": 2.0,
                    "pm10_ug_m3": pm + 5,
                    "co_ug_m3": 1.0,
                    "no2_ug_m3": 40.0,
                    "hours_into_episode": 0,
                    "in_episode_flag": 0,
                    "hour": t.hour,
                    "month": t.month,
                    "day_of_week": t.isoweekday(),
                    "season_code": 0,
                    "cluster_id": sk % 2,
                    "cluster_label": "elevated_core" if sk % 2 == 0 else "cleaner_fringe",
                    "season": "winter",
                }
            )
    return pd.DataFrame(rows)


def test_sequence_y_matches_origin_target():
    df = _toy_matrix(n_hours=30, station_keys=(1,))
    seq = build_sequences(df, seq_len=LSTM_SEQ_LEN)
    assert seq.X.shape[1] == LSTM_SEQ_LEN
    assert seq.X.shape[2] == len(LSTM_SEQ_COLS)
    # Last timestep PM2.5 equals meta origin pm25
    assert np.allclose(seq.X[:, -1, 0], seq.meta["pm25_ug_m3"].to_numpy())
    assert np.allclose(seq.y, seq.meta[TARGET_COL].to_numpy())


def test_sequence_does_not_look_at_future_pm25():
    df = _toy_matrix(n_hours=30, station_keys=(1,))
    seq = build_sequences(df, seq_len=24)
    # For origin i (0-based in station), window uses rows i-23..i; never i+1
    sub = df.sort_values("event_time_local").reset_index(drop=True)
    # First valid origin index = 23
    origin = 23
    expected = sub.loc[origin - 23 : origin, "pm25_ug_m3"].to_numpy(dtype=float)
    assert np.allclose(seq.X[0, :, 0], expected)
    # Target is next hour after origin — not in the window features
    assert seq.y[0] == pytest.approx(float(sub.loc[origin, TARGET_COL]))
    assert seq.y[0] != pytest.approx(seq.X[0, -1, 0])


def test_stations_do_not_mix():
    df = _toy_matrix(n_hours=30, station_keys=(1, 2))
    seq = build_sequences(df, seq_len=24)
    assert set(seq.meta["station_key"].unique()) == {1, 2}
    # Station embedding ids distinct
    id_map = seq.station_to_id
    for sk, sid in zip(seq.meta["station_key"], seq.station_ids):
        assert sid == id_map[int(sk)]


def test_gap_drops_incomplete_window():
    full_df = _toy_matrix(n_hours=60, station_keys=(1,))
    full = build_sequences(full_df, seq_len=24)
    # Remove a middle hour so windows that cross the gap are dropped
    gapped = full_df.drop(index=full_df.index[30]).reset_index(drop=True)
    seq = build_sequences(gapped, seq_len=24)
    assert len(seq.y) < len(full.y)
    assert len(seq.y) > 0


def test_scaler_train_only_and_model_forward():
    df = _toy_matrix(n_hours=40, station_keys=(1, 2))
    # Force some val rows
    df.loc[df["event_time_local"] >= "2015-01-02", "split"] = "val"
    seq = build_sequences(df, seq_len=24)
    scaler = fit_scaler_on_train(seq)
    Xs = transform_sequences(seq, scaler)
    assert Xs.dtype == np.float32
    train_flat = Xs[seq.meta["split"] == "train"].reshape(-1, Xs.shape[-1])
    assert abs(float(train_flat.mean())) < 0.15

    model = Pm25LSTM(n_features=Xs.shape[-1], n_stations=len(seq.station_to_id))
    xb = torch.from_numpy(Xs[:4])
    sb = torch.from_numpy(seq.station_ids[:4])
    out = model(xb, sb)
    assert out.shape == (4,)


def test_station_id_map_stable():
    assert build_station_id_map([3, 1, 2, 1]) == {1: 0, 2: 1, 3: 2}
