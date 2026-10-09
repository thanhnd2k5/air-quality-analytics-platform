"""Chronological train/val/test assignment (no random split)."""

from __future__ import annotations

import pandas as pd

from src.forecasting.constants import (
    ML_END,
    ML_START,
    TEST_END,
    TEST_START,
    TRAIN_END,
    VAL_END,
    VAL_START,
)


def assign_split(
    event_time: pd.Series,
    *,
    train_end: str = TRAIN_END,
    val_start: str = VAL_START,
    val_end: str = VAL_END,
    test_start: str = TEST_START,
    test_end: str = TEST_END,
    ml_start: str = ML_START,
    ml_end: str = ML_END,
) -> pd.Series:
    """Label each timestamp train / val / test; outside ML window → NA."""
    ts = pd.to_datetime(event_time)
    t_train_end = pd.Timestamp(train_end)
    t_val_start = pd.Timestamp(val_start)
    t_val_end = pd.Timestamp(val_end)
    t_test_start = pd.Timestamp(test_start)
    t_test_end = pd.Timestamp(test_end)
    t_ml_start = pd.Timestamp(ml_start)
    t_ml_end = pd.Timestamp(ml_end)

    out = pd.Series(pd.NA, index=ts.index, dtype="string")
    in_ml = (ts >= t_ml_start) & (ts <= t_ml_end)
    out.loc[in_ml & (ts <= t_train_end)] = "train"
    out.loc[in_ml & (ts >= t_val_start) & (ts <= t_val_end)] = "val"
    out.loc[in_ml & (ts >= t_test_start) & (ts <= t_test_end)] = "test"
    return out
