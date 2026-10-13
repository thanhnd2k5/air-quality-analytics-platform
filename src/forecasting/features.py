"""Causal feature engineering for PM2.5(t+1h)."""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pandas as pd

from src.forecasting.constants import (
    EPISODE_MIN_HOURS,
    EPISODE_THRESHOLD,
    FEATURE_COLS,
    FEATURE_COLS_V2,
    FEATURE_COLS_V3,
    META_COLS,
    PM25_LAGS,
    PM25_ROLL_WINDOWS,
    POLLUTANT_COLS,
    POLLUTANT_COLS_V3,
    POLLUTANT_LAGS,
    SEASON_TO_CODE,
    TARGET_COL,
    WEATHER_COLS,
    WEATHER_COLS_V3,
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
    return out


def add_pm25_delta(df: pd.DataFrame) -> pd.DataFrame:
    """Short-term change: PM2.5(t) − PM2.5(t−1). Requires pm25_lag_1."""
    out = df.copy()
    out["pm25_delta_1"] = out["pm25_ug_m3"] - out["pm25_lag_1"]
    return out


def add_weather_lags_and_missing_flags(
    df: pd.DataFrame,
    *,
    weather_cols: Sequence[str] = WEATHER_COLS,
) -> pd.DataFrame:
    out = df.copy()
    for col in weather_cols:
        if col not in out.columns:
            out[col] = np.nan
        out[f"{col}_missing"] = out[col].isna().astype(np.int8)
        out[f"{col}_lag_{WEATHER_LAG}"] = _groupby_station(out)[col].shift(WEATHER_LAG)
    return out


def add_pollutant_lags_and_missing_flags(
    df: pd.DataFrame,
    *,
    pollutant_cols: Sequence[str] = POLLUTANT_COLS,
) -> pd.DataFrame:
    """Co-pollutant value at t, lags, and pre-impute missing flags."""
    out = df.copy()
    for col in pollutant_cols:
        if col not in out.columns:
            out[col] = np.nan
        out[f"{col}_missing"] = out[col].isna().astype(np.int8)
        g = _groupby_station(out)[col]
        for k in POLLUTANT_LAGS:
            out[f"{col}_lag_{k}"] = g.shift(k)
    return out


def _causal_dirty_streak(pm25: np.ndarray, *, threshold: float) -> np.ndarray:
    """Consecutive dirty hours ending at each index (0 if not dirty at t). Causal."""
    streak = np.zeros(len(pm25), dtype=np.int32)
    cur = 0
    for i, v in enumerate(pm25):
        if np.isfinite(v) and float(v) >= threshold:
            cur += 1
        else:
            cur = 0
        streak[i] = cur
    return streak


def add_causal_episode_features(
    df: pd.DataFrame,
    *,
    threshold: float = EPISODE_THRESHOLD,
    min_hours: int = EPISODE_MIN_HOURS,
) -> pd.DataFrame:
    """
    Causal episode proxies from PM2.5 history ≤ t only.

    hours_into_episode = consecutive dirty hours ending at t.
    in_episode_flag = 1 when streak ≥ min_hours (known without future).
    """
    out = df.copy()
    hours = pd.Series(0, index=out.index, dtype=np.int32)
    for _, station_df in out.groupby("station_key", sort=False):
        ordered = station_df.sort_values("event_time_local")
        streak = _causal_dirty_streak(
            ordered["pm25_ug_m3"].to_numpy(dtype=float),
            threshold=threshold,
        )
        hours.loc[ordered.index] = streak
    out["hours_into_episode"] = hours.astype(np.int32)
    out["in_episode_flag"] = (out["hours_into_episode"] >= min_hours).astype(np.int8)
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
    ]
    return df.dropna(subset=required).reset_index(drop=True)


def impute_weather_from_train(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float]]:
    """Fill weather NaNs with train-split medians (leakage-safe)."""
    return impute_numeric_from_train(
        df,
        cols=list(WEATHER_COLS) + [f"{c}_lag_{WEATHER_LAG}" for c in WEATHER_COLS],
    )


def impute_numeric_from_train(
    df: pd.DataFrame,
    cols: Sequence[str],
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Fill listed numeric NaNs with train-split medians (leakage-safe)."""
    out = df.copy()
    train_mask = out["split"] == "train"
    medians: dict[str, float] = {}
    for col in cols:
        if col not in out.columns:
            continue
        med = float(out.loc[train_mask, col].median(skipna=True))
        if np.isnan(med):
            med = 0.0
        medians[col] = med
        out[col] = out[col].fillna(med)
    return out, medians


def _pollutant_impute_cols(
    pollutant_cols: Sequence[str] = POLLUTANT_COLS,
) -> list[str]:
    cols: list[str] = list(pollutant_cols)
    for c in pollutant_cols:
        for k in POLLUTANT_LAGS:
            cols.append(f"{c}_lag_{k}")
    return cols


def _weather_impute_cols(weather_cols: Sequence[str] = WEATHER_COLS) -> list[str]:
    return list(weather_cols) + [f"{c}_lag_{WEATHER_LAG}" for c in weather_cols]


def build_feature_matrix(base: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Full P10b transform: calendar → lags/rolls → weather flags → target → split
    → drop unusable → weather impute from train.
    """
    if base.empty:
        raise ValueError("Empty forecast base frame")

    df = base.sort_values(["station_key", "event_time_local"]).reset_index(drop=True)
    n_in = len(df)

    df = add_calendar_codes(df)
    df = add_pm25_lags_and_rolls(df)
    df = add_weather_lags_and_missing_flags(df)
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
        "variant": "v1",
    }
    return df, meta


def build_feature_matrix_v2(base: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Vòng A matrix: v1 features + delta + co-pollutant lags + causal episode flags.
    Pollutant NaNs imputed with train medians (same policy as weather).
    """
    if base.empty:
        raise ValueError("Empty forecast base frame")

    df = base.sort_values(["station_key", "event_time_local"]).reset_index(drop=True)
    n_in = len(df)

    df = add_calendar_codes(df)
    df = add_pm25_lags_and_rolls(df)
    df = add_pm25_delta(df)
    df = add_weather_lags_and_missing_flags(df)
    df = add_pollutant_lags_and_missing_flags(df)
    df = add_causal_episode_features(df)
    df = add_target(df)
    df["split"] = assign_split(df["event_time_local"])

    before_drop = len(df)
    df = drop_unusable_rows(df)
    after_drop = len(df)

    df = df[df["split"].isin(["train", "val", "test"])].reset_index(drop=True)

    weather_cols = _weather_impute_cols()
    pollutant_cols = _pollutant_impute_cols()
    df, medians = impute_numeric_from_train(df, cols=weather_cols + pollutant_cols)
    weather_medians = {k: v for k, v in medians.items() if k in weather_cols}
    pollutant_medians = {k: v for k, v in medians.items() if k in pollutant_cols}

    meta = {
        "rows_in": n_in,
        "rows_before_drop": before_drop,
        "rows_after_target_lag_drop": after_drop,
        "rows_out": len(df),
        "split_counts": df["split"].value_counts().to_dict(),
        "weather_train_medians": weather_medians,
        "pollutant_train_medians": pollutant_medians,
        "feature_cols": list(FEATURE_COLS_V2),
        "target_col": TARGET_COL,
        "meta_cols": list(META_COLS),
        "variant": "v2",
        "episode_threshold": EPISODE_THRESHOLD,
        "episode_min_hours": EPISODE_MIN_HOURS,
    }
    return df, meta


def build_feature_matrix_v3(base: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Feature v3: v2 + O3/SO2 pollutant lags + cloud_cover (weather-style).
    Train-median impute for weather_v3 + pollutant_v3 columns.
    """
    if base.empty:
        raise ValueError("Empty forecast base frame")

    df = base.sort_values(["station_key", "event_time_local"]).reset_index(drop=True)
    n_in = len(df)

    df = add_calendar_codes(df)
    df = add_pm25_lags_and_rolls(df)
    df = add_pm25_delta(df)
    df = add_weather_lags_and_missing_flags(df, weather_cols=WEATHER_COLS_V3)
    df = add_pollutant_lags_and_missing_flags(df, pollutant_cols=POLLUTANT_COLS_V3)
    df = add_causal_episode_features(df)
    df = add_target(df)
    df["split"] = assign_split(df["event_time_local"])

    before_drop = len(df)
    df = drop_unusable_rows(df)
    after_drop = len(df)

    df = df[df["split"].isin(["train", "val", "test"])].reset_index(drop=True)

    weather_cols = _weather_impute_cols(WEATHER_COLS_V3)
    pollutant_cols = _pollutant_impute_cols(POLLUTANT_COLS_V3)
    df, medians = impute_numeric_from_train(df, cols=weather_cols + pollutant_cols)
    weather_medians = {k: v for k, v in medians.items() if k in weather_cols}
    pollutant_medians = {k: v for k, v in medians.items() if k in pollutant_cols}

    meta = {
        "rows_in": n_in,
        "rows_before_drop": before_drop,
        "rows_after_target_lag_drop": after_drop,
        "rows_out": len(df),
        "split_counts": df["split"].value_counts().to_dict(),
        "weather_train_medians": weather_medians,
        "pollutant_train_medians": pollutant_medians,
        "feature_cols": list(FEATURE_COLS_V3),
        "target_col": TARGET_COL,
        "meta_cols": list(META_COLS),
        "variant": "v3",
        "episode_threshold": EPISODE_THRESHOLD,
        "episode_min_hours": EPISODE_MIN_HOURS,
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
        finding: dict[str, Any] = {
            "station_key": int(sk),
            "event_time_local": str(row["event_time_local"]),
            "lag1_matches_prev_pm25": bool(lag_ok),
            "target_matches_next_pm25": bool(tgt_ok),
        }
        if "pm25_delta_1" in sub.columns and not pd.isna(row.get("pm25_lag_1")):
            expected_delta = float(row["pm25_ug_m3"]) - float(row["pm25_lag_1"])
            finding["delta1_matches_pm25_minus_lag1"] = bool(
                pd.isna(row.get("pm25_delta_1"))
                or float(row["pm25_delta_1"]) == expected_delta
            )
        if "hours_into_episode" in sub.columns:
            # Streak at i must not depend on future: recompute from prefix only.
            prefix = sub.iloc[: i + 1]["pm25_ug_m3"].to_numpy(dtype=float)
            expected_streak = int(_causal_dirty_streak(prefix, threshold=EPISODE_THRESHOLD)[-1])
            finding["episode_streak_matches_prefix"] = int(row["hours_into_episode"]) == expected_streak
        findings.append(finding)
    return findings
