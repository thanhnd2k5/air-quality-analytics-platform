"""Build the alert label PM2.5(t+h) ≥ threshold from the forecasting feature matrix."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.classification.constants import (
    ALERT_TARGET_COL,
    ALERT_THRESHOLD,
    HORIZON_HOURS,
    TARGET_PM25_COL,
)
from src.forecasting.constants import TARGET_COL


def alert_label(values, threshold: float = ALERT_THRESHOLD) -> np.ndarray:
    """1 when PM2.5 ≥ threshold, else 0 (NaN must be removed before calling)."""
    return (np.asarray(values, dtype=float) >= threshold).astype(int)


def observed_pm25_lookup(df: pd.DataFrame) -> pd.Series:
    """Observed hourly PM2.5 indexed by (station_key, time).

    Combines the value at origin time (``pm25_ug_m3`` @ event_time) with the
    t+1 target (``y_pm25_tplus1`` @ target_time) so hours that only appear as a
    target are still available for longer horizons.
    """
    at_origin = df[["station_key", "event_time_local", "pm25_ug_m3"]].rename(
        columns={"event_time_local": "time", "pm25_ug_m3": "pm25"}
    )
    at_target = df[["station_key", "target_time_local", TARGET_COL]].rename(
        columns={"target_time_local": "time", TARGET_COL: "pm25"}
    )
    both = pd.concat([at_origin, at_target], ignore_index=True).dropna(subset=["pm25"])
    both = both.drop_duplicates(subset=["station_key", "time"], keep="first")
    return both.set_index(["station_key", "time"])["pm25"]


def add_alert_target(
    df: pd.DataFrame,
    *,
    horizon: int = HORIZON_HOURS,
    threshold: float = ALERT_THRESHOLD,
) -> pd.DataFrame:
    """Return a copy with ``target_time_local``, ``y_pm25_target`` and ``y_alert``.

    horizon=1 reuses the regression target column; larger horizons look up the
    observed PM2.5 at event_time + horizon for the same station. Rows without an
    observed target are dropped.
    """
    if horizon < 1:
        raise ValueError("horizon must be ≥ 1 hour")
    out = df.copy()
    out["event_time_local"] = pd.to_datetime(out["event_time_local"])
    if horizon == 1:
        out["target_time_local"] = pd.to_datetime(out["target_time_local"])
        out[TARGET_PM25_COL] = out[TARGET_COL].astype(float)
    else:
        lookup = observed_pm25_lookup(out)
        out["target_time_local"] = out["event_time_local"] + pd.Timedelta(hours=horizon)
        keys = pd.MultiIndex.from_arrays([out["station_key"], out["target_time_local"]])
        out[TARGET_PM25_COL] = lookup.reindex(keys).to_numpy()
    out = out.dropna(subset=[TARGET_PM25_COL]).reset_index(drop=True)
    out[ALERT_TARGET_COL] = alert_label(out[TARGET_PM25_COL], threshold)
    return out
