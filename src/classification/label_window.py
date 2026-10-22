"""Keep a split's label inside that split.

The published matrix assigns ``split`` from the origin hour. The alert label
is a later hour, so the last origins of train and validation can take their
label from the next period. An origin stays in a split only when every hour
the label needs is still on or before that split's end.

The cuts below were fixed before the hygiene counts. They are the locked
chronological split plus three development folds on shared timestamps.
2016 H2 is not one of those folds.
"""

from __future__ import annotations

from typing import Mapping, NamedTuple

import pandas as pd

from src.forecasting.constants import (
    ML_START,
    TEST_END,
    TRAIN_END,
    VAL_END,
)

# Point alert at t+h. The onset label needs a 3-hour run that may start at
# t+6, so the last hour it may read is t+8.
POINT_LABEL_HOURS = 1
ONSET_CONFIRM_HOURS = 8
LABEL_CENSUS_HOURS = (1, 3, 6, ONSET_CONFIRM_HOURS)


class TimeFold(NamedTuple):
    name: str
    train_end: str
    val_start: str
    val_end: str


# Expanding windows on the development period. Validation never enters 2016 H2.
DEVELOPMENT_FOLDS = (
    TimeFold("2015", "2014-12-31 23:00:00", "2015-01-01 00:00:00", "2015-12-31 23:00:00"),
    TimeFold("2015h2", "2015-06-30 23:00:00", "2015-07-01 00:00:00", "2015-12-31 23:00:00"),
    TimeFold("2016h1", "2015-12-31 23:00:00", "2016-01-01 00:00:00", "2016-06-30 23:00:00"),
)

PUBLISHED_SPLIT_ENDS = {
    "train": TRAIN_END,
    "val": VAL_END,
    "test": TEST_END,
}


def split_ends_for_fold(fold: TimeFold) -> dict[str, str]:
    return {"train": fold.train_end, "val": fold.val_end}


def assign_time_fold(
    event_time: pd.Series,
    fold: TimeFold,
    *,
    ml_start: str = ML_START,
) -> pd.Series:
    """Label origins train or val on a shared clock. Hours in a gap stay unlabeled."""
    ts = pd.to_datetime(pd.Series(event_time))
    start = pd.Timestamp(ml_start)
    train_end = pd.Timestamp(fold.train_end)
    val_start = pd.Timestamp(fold.val_start)
    val_end = pd.Timestamp(fold.val_end)
    out = pd.Series(pd.NA, index=ts.index, dtype="string")
    out.loc[(ts >= start) & (ts <= train_end)] = "train"
    out.loc[(ts >= val_start) & (ts <= val_end)] = "val"
    return out


def rows_inside_split(
    event_time: pd.Series,
    split: pd.Series,
    split_end: Mapping[str, str],
    *,
    label_hours: int,
    deadline: pd.Series | None = None,
) -> pd.Series:
    """True when the label's last hour is on or before the origin's split end.

    ``label_hours`` is the offset from the origin when ``deadline`` is omitted.
    Pass ``deadline`` when the matrix already stores the label timestamp.
    """
    if label_hours < 1:
        raise ValueError("label_hours must be ≥ 1")
    if deadline is None:
        last_hour = pd.to_datetime(event_time) + pd.Timedelta(hours=label_hours)
    else:
        last_hour = pd.to_datetime(deadline)
    ends = split.map({name: pd.Timestamp(value) for name, value in split_end.items()})
    known = split.isin(list(split_end))
    return known & last_hour.notna() & ends.notna() & (last_hour <= ends)
