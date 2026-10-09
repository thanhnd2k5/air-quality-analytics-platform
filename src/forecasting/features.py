"""Causal feature engineering for PM2.5(t+1h)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.forecasting.constants import (
    EPISODE_MIN_HOURS,
    EPISODE_THRESHOLD_UG_M3,
    FEATURE_COLS,
    META_COLS,
    PM25_LAGS,
    PM25_ROLL_WINDOWS,
    POLLUTANT_LAG,
    POLLUTANT_LAG_COLS,
    SEASON_TO_CODE,
    TARGET_COL,
    WEATHER_COLS,
    WEATHER_LAG,
)
from src.forecasting.split import assign_split


def _groupby_station(df: pd.DataFrame) -> pd.core.groupby.generic.DataFrameGroupBy:
    return df.groupby("station_key", sort=False)


def add_calendar_codes(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["season_code"] = out["season"].map(SEASON_TO_CODE).astype("Int64")
    return out


def add_pm25_lags_and_rolls(df: pd.DataFrame) -> pd.DataFrame:
    """Lags and rolling means ending at t (uses pm25 ≤ t only)."""
    out = df.copy()
    g = _groupby_station(out)["pm25_ug_m3"]
    for k in PM25_LAGS:
        out[f"pm25_lag_{k}"] = g.shift(k)
    for w in PM25_ROLL_WINDOWS:
        # rolling includes current hour t — allowed at prediction time.
        out[f"pm25_roll_mean_{w}"] = (
            g.rolling(window=w, min_periods=max(1, w // 2)).mean().reset_index(level=0, drop=True)
        )
    # Short-term change at t (needs lag_1).
    out["pm25_delta_1"] = out["pm25_ug_m3"] - out["pm25_lag_1"]
    return out


def add_weather_lags_and_missing_flags(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in WEATHER_COLS:
        out[f"{col}_missing"] = out[col].isna().astype(np.int8)
        out[f"{col}_lag_{WEATHER_LAG}"] = _groupby_station(out)[col].shift(WEATHER_LAG)
    return out


def add_pollutant_lags_and_missing_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Lag-1 co-pollutants + missing flags (nulls filled later from train)."""
    out = df.copy()
    for col in POLLUTANT_LAG_COLS:
        if col not in out.columns:
            out[col] = np.nan
        lag_name = f"{col}_lag_{POLLUTANT_LAG}"
        miss_name = f"{lag_name}_missing"
        out[lag_name] = _groupby_station(out)[col].shift(POLLUTANT_LAG)
        out[miss_name] = out[lag_name].isna().astype(np.int8)
    return out


def _causal_episode_arrays(
    pm25: np.ndarray,
    *,
    threshold: float = EPISODE_THRESHOLD_UG_M3,
    min_hours: int = EPISODE_MIN_HOURS,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-station causal episode stats from PM2.5 history ≤ t only.

    - dirty hour: pm25 >= threshold and not null (null breaks the run)
    - hours_into_dirty_run: consecutive dirty hours ending at t
    - in_episode_flag: 1 iff streak >= min_hours (no look-ahead to future hours)
    - hours_since_last_episode: hours since last in_episode hour (NaN before first)
    """
    dirty = (pm25 >= threshold) & ~np.isnan(pm25)
    n = len(dirty)
    streak = np.zeros(n, dtype=np.int32)
    run = 0
    for i, is_dirty in enumerate(dirty):
        run = run + 1 if is_dirty else 0
        streak[i] = run
    in_ep = (streak >= min_hours).astype(np.int8)
    since = np.full(n, np.nan, dtype=np.float64)
    last = -1
    for i in range(n):
        if in_ep[i]:
            last = i
            since[i] = 0.0
        elif last >= 0:
            since[i] = float(i - last)
    return streak, in_ep, since


def add_episode_features(df: pd.DataFrame) -> pd.DataFrame:
    """Causal episode features aligned with Phase 8c rule (no future leakage)."""
    out = df.copy()
    out["hours_into_dirty_run"] = np.int32(0)
    out["in_episode_flag"] = np.int8(0)
    out["hours_since_last_episode"] = np.nan
    for _, idx in out.groupby("station_key", sort=False).groups.items():
        station_df = out.loc[idx].sort_values("event_time_local")
        pm = station_df["pm25_ug_m3"].to_numpy(dtype=float)
        streak, in_ep, since = _causal_episode_arrays(pm)
        ordered = station_df.index
        out.loc[ordered, "hours_into_dirty_run"] = streak
        out.loc[ordered, "in_episode_flag"] = in_ep
        out.loc[ordered, "hours_since_last_episode"] = since
    out["in_episode_flag"] = out["in_episode_flag"].astype(np.int8)
    return out


def add_target(df: pd.DataFrame) -> pd.DataFrame:
    """y = PM2.5 at t+1 within station (not available as a feature)."""
    out = df.copy()
    out[TARGET_COL] = _groupby_station(out)["pm25_ug_m3"].shift(-1)
    out["target_time_local"] = out["event_time_local"] + pd.Timedelta(hours=1)
    return out


def drop_unusable_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows without target, current PM2.5(t), or any lag/roll (need 24h history)."""
    required = [
        TARGET_COL,
        "pm25_ug_m3",
        *(f"pm25_lag_{k}" for k in PM25_LAGS),
        *(f"pm25_roll_mean_{w}" for w in PM25_ROLL_WINDOWS),
        "pm25_delta_1",
    ]
    return df.dropna(subset=required).reset_index(drop=True)


def impute_weather_from_train(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float]]:
    """Fill weather / pollutant-lag / episode-since NaNs with train medians (leakage-safe)."""
    out = df.copy()
    train_mask = out["split"] == "train"
    medians: dict[str, float] = {}
    cols = (
        list(WEATHER_COLS)
        + [f"{c}_lag_{WEATHER_LAG}" for c in WEATHER_COLS]
        + [f"{c}_lag_{POLLUTANT_LAG}" for c in POLLUTANT_LAG_COLS]
        + ["hours_since_last_episode"]
    )
    for col in cols:
        if col not in out.columns:
            continue
        med = float(out.loc[train_mask, col].median(skipna=True))
        if np.isnan(med):
            med = 0.0
        medians[col] = med
        out[col] = out[col].fillna(med)
    return out, medians


def build_feature_matrix(base: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Full P10b transform: calendar → lags/rolls → weather/pollutant → episode
    → target → split → drop unusable → train-median impute.
    """
    if base.empty:
        raise ValueError("Empty forecast base frame")

    df = base.sort_values(["station_key", "event_time_local"]).reset_index(drop=True)
    n_in = len(df)

    df = add_calendar_codes(df)
    df = add_pm25_lags_and_rolls(df)
    df = add_weather_lags_and_missing_flags(df)
    df = add_pollutant_lags_and_missing_flags(df)
    df = add_episode_features(df)
    df = add_target(df)
    df["split"] = assign_split(df["event_time_local"])

    before_drop = len(df)
    df = drop_unusable_rows(df)
    after_drop = len(df)

    # Rows outside labeled splits should not remain (ML window only).
    df = df[df["split"].isin(["train", "val", "test"])].reset_index(drop=True)

    df, weather_medians = impute_weather_from_train(df)

    meta = {
        "rows_in": n_in,
        "rows_before_drop": before_drop,
        "rows_after_target_lag_drop": after_drop,
        "rows_out": len(df),
        "split_counts": df["split"].value_counts().to_dict(),
        "weather_train_medians": weather_medians,
        "feature_cols": list(FEATURE_COLS),
        "target_col": TARGET_COL,
        "meta_cols": list(META_COLS),
        "feature_set_version": "v1_1_episode_pollutant",
    }
    return df, meta


def leakage_spot_check(df: pd.DataFrame, *, n_stations: int = 2) -> list[dict[str, Any]]:
    """
    For a few stations, verify lag_1 == previous pm25 and target == next pm25
    on the raw timeline (before drop, caller should pass engineered frame with nulls ok).
    """
    findings: list[dict[str, Any]] = []
    stations = sorted(df["station_key"].unique())[:n_stations]
    for sk in stations:
        sub = df[df["station_key"] == sk].sort_values("event_time_local")
        if len(sub) < 3:
            continue
        # Middle row with both neighbors present
        i = len(sub) // 2
        row = sub.iloc[i]
        prev = sub.iloc[i - 1]
        nxt = sub.iloc[i + 1]
        lag_ok = (
            pd.isna(row.get("pm25_lag_1"))
            or pd.isna(prev["pm25_ug_m3"])
            or float(row["pm25_lag_1"]) == float(prev["pm25_ug_m3"])
        )
        tgt_ok = (
            pd.isna(row.get(TARGET_COL))
            or pd.isna(nxt["pm25_ug_m3"])
            or float(row[TARGET_COL]) == float(nxt["pm25_ug_m3"])
        )
        findings.append(
            {
                "station_key": int(sk),
                "event_time_local": str(row["event_time_local"]),
                "lag1_matches_prev_pm25": bool(lag_ok),
                "target_matches_next_pm25": bool(tgt_ok),
            }
        )
    return findings
