"""Six-hour episode-onset labels and the comparison rule.

The question is: the station is still below 115 µg/m³ now; does a run of at
least three hours at or above 115 start in the next six hours?

These cuts were written before the onset fit. A positive label is confirmed
only from hours t+1 through t+8. The comparison spends at most half a false
alarm per eligible station-day on validation, and a model has to clear the
chosen baseline by 0.05 episode recall on at least two development folds.
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pandas as pd

from src.clustering.window_profiles import episode_runs, meteorological_season
from src.forecasting.constants import EPISODE_MIN_HOURS, EPISODE_THRESHOLD

ONSET_WINDOW_HOURS = 6
ONSET_CONFIRM_HOURS = ONSET_WINDOW_HOURS + EPISODE_MIN_HOURS - 1
PRIMARY_FA_PER_STATION_DAY = 0.5
SENSITIVITY_FA_PER_STATION_DAY = 1.0
RECALL_MARGIN = 0.05
FOLDS_REQUIRED = 2
PROBABILITY_GRID = tuple(round(0.05 * i, 2) for i in range(1, 20))
LEVEL_GRID = (40, 50, 60, 70, 75, 80, 90, 100, 105, 110)
TREND_GRID = (50, 75, 90, 100, 110, 115, 130, 150, 175, 200, 250, 300, 400)


def trend_score(pm25, delta) -> np.ndarray:
    """Level reached if the last hour's rise, and not a fall, continues for six hours."""
    level = np.asarray(pm25, dtype=float)
    change = np.asarray(delta, dtype=float)
    change = np.where(np.isfinite(change), change, 0.0)
    return level + ONSET_WINDOW_HOURS * np.maximum(change, 0.0)


def episode_catalog(hourly: pd.DataFrame) -> pd.DataFrame:
    """Episode start, duration, peak, and season. Null PM2.5 breaks a run."""
    frame = hourly.drop_duplicates(["station_key", "event_time_local"]).copy()
    frame["event_time_local"] = pd.to_datetime(frame["event_time_local"])
    episodes = episode_runs(frame)
    if episodes.empty:
        episodes["peak_pm25"] = pd.Series(dtype=float)
        episodes["season"] = pd.Series(dtype="string")
        return episodes
    peaks: list[float] = []
    grouped = {
        int(key): station.sort_values("event_time_local")
        for key, station in frame.groupby("station_key", sort=False)
    }
    for row in episodes.itertuples(index=False):
        station = grouped[int(row.station_key)]
        times = pd.to_datetime(station["event_time_local"]).to_numpy(dtype="datetime64[ns]")
        values = station["pm25_ug_m3"].to_numpy(dtype=float)
        start = np.datetime64(pd.Timestamp(row.start_time).to_datetime64())
        begin = int(np.searchsorted(times, start, side="left"))
        end = begin + int(row.duration_hours)
        peaks.append(float(np.nanmax(values[begin:end])))
    episodes = episodes.copy()
    episodes["peak_pm25"] = peaks
    episodes["season"] = meteorological_season(pd.to_datetime(episodes["start_time"]).dt.month).to_numpy()
    return episodes


def mark_onset_origins(
    origins: pd.DataFrame,
    hourly: pd.DataFrame,
    *,
    window_hours: int = ONSET_WINDOW_HOURS,
    confirm_hours: int = ONSET_CONFIRM_HOURS,
) -> pd.DataFrame:
    """Mark each origin. Ineligible rows keep a null label.

    Eligible means PM2.5(t) is observed and below the episode threshold, and
    every clock hour from t+1 through t+confirm exists for that station. A
    null inside that span breaks a run; it does not drop the origin. The
    split cutoff is applied by the caller.
    """
    if confirm_hours < window_hours + EPISODE_MIN_HOURS - 1:
        raise ValueError("confirm_hours must cover a 3-hour run starting at the end of the window")
    catalog = episode_catalog(hourly)
    clock = hourly.drop_duplicates(["station_key", "event_time_local"]).copy()
    clock["event_time_local"] = pd.to_datetime(clock["event_time_local"])
    by_station_times = {
        int(key): pd.to_datetime(station["event_time_local"]).to_numpy(dtype="datetime64[ns]")
        for key, station in clock.groupby("station_key", sort=False)
    }
    by_station_episodes = {
        int(key): station.sort_values("start_time")
        for key, station in catalog.groupby("station_key", sort=False)
    }

    out = origins.copy().reset_index(drop=True)
    out["event_time_local"] = pd.to_datetime(out["event_time_local"])
    n = len(out)
    clock_ok = np.zeros(n, dtype=bool)
    labels = np.zeros(n, dtype=np.int8)
    lead = np.full(n, np.nan)
    duration = np.full(n, np.nan)
    peak = np.full(n, np.nan)
    starts = np.full(n, np.datetime64("NaT", "ns"))
    pm25 = out["pm25_ug_m3"].to_numpy(dtype=float)
    clean_now = np.isfinite(pm25) & (pm25 < EPISODE_THRESHOLD)

    for station_key, station in out.groupby("station_key", sort=False):
        idx = station.index.to_numpy()
        times = pd.to_datetime(station["event_time_local"]).to_numpy(dtype="datetime64[ns]")
        observed = by_station_times.get(int(station_key))
        if observed is None or len(observed) == 0:
            continue
        present = np.ones(len(times), dtype=bool)
        for hour in range(1, confirm_hours + 1):
            present &= np.isin(times + np.timedelta64(hour, "h"), observed)
        clock_ok[idx] = present
        episodes = by_station_episodes.get(int(station_key))
        if episodes is None or episodes.empty:
            continue
        episode_starts = pd.to_datetime(episodes["start_time"]).to_numpy(dtype="datetime64[ns]")
        position = np.searchsorted(episode_starts, times, side="right")
        has_later = position < len(episode_starts)
        chosen = np.full(len(times), np.datetime64("NaT", "ns"))
        chosen[has_later] = episode_starts[position[has_later]]
        delta = (chosen - times) / np.timedelta64(1, "h")
        in_window = has_later & np.isfinite(delta) & (delta >= 1) & (delta <= window_hours)
        take = np.flatnonzero(in_window)
        if len(take) == 0:
            continue
        labels[idx[take]] = 1
        lead[idx[take]] = delta[take]
        starts[idx[take]] = chosen[take]
        mapped = position[take]
        duration[idx[take]] = episodes["duration_hours"].to_numpy()[mapped]
        peak[idx[take]] = episodes["peak_pm25"].to_numpy()[mapped]

    eligible = clock_ok & clean_now
    out["onset_clock_ok"] = clock_ok
    out["onset_clean_now"] = clean_now
    out["y_onset"] = pd.Series(pd.NA, index=out.index, dtype="Int64")
    out.loc[eligible, "y_onset"] = labels[eligible].astype(int)
    out["lead_hours"] = lead
    out.loc[~eligible, "lead_hours"] = np.nan
    out["episode_start"] = pd.to_datetime(starts)
    out.loc[~eligible | (labels == 0), "episode_start"] = pd.NaT
    out["episode_duration_h"] = duration
    out["episode_peak"] = peak
    out.loc[~eligible | (labels == 0), ["episode_duration_h", "episode_peak"]] = np.nan
    return out


def episode_metrics(frame: pd.DataFrame, pred: Sequence[int]) -> dict[str, Any]:
    """Event recall, lead time, and false alarms per eligible station-day."""
    work = frame.reset_index(drop=True)
    predicted = np.asarray(pred, dtype=int)
    if len(predicted) != len(work):
        raise ValueError("pred length does not match the frame")
    y = work["y_onset"].to_numpy(dtype=int)
    day = pd.to_datetime(work["event_time_local"]).dt.strftime("%Y-%m-%d")
    day_id = work["station_key"].astype(str) + "|" + day
    n_days = int(day_id.nunique())
    false_positive = (predicted == 1) & (y == 0)
    true_positive = (predicted == 1) & (y == 1)
    n_fp = int(false_positive.sum())
    n_tp = int(true_positive.sum())
    n_alerts = n_fp + n_tp
    positives = work.loc[y == 1].copy()
    positives["_pred"] = predicted[y == 1]
    if positives.empty:
        n_episodes = 0
        n_detected = 0
        recall = float("nan")
        median_lead = float("nan")
        frac_lead_ge_3 = float("nan")
        median_alerts = float("nan")
    else:
        grouped = positives.groupby(["station_key", "episode_start"], sort=False)
        detected = grouped["_pred"].max()
        n_episodes = int(len(detected))
        n_detected = int((detected == 1).sum())
        recall = float(n_detected / n_episodes) if n_episodes else float("nan")
        hits = positives.loc[positives["_pred"] == 1]
        if hits.empty:
            median_lead = float("nan")
            frac_lead_ge_3 = float("nan")
            median_alerts = float("nan")
        else:
            lead = hits.groupby(["station_key", "episode_start"], sort=False)["lead_hours"].max()
            alerts = hits.groupby(["station_key", "episode_start"], sort=False).size()
            median_lead = float(lead.median())
            frac_lead_ge_3 = float((lead >= 3).mean())
            median_alerts = float(alerts.median())
    days_with_fp = int(day_id[false_positive].nunique()) if n_fp else 0
    return {
        "n_origins": int(len(work)),
        "n_positive_origins": int(y.sum()),
        "n_episodes": n_episodes,
        "n_detected": n_detected,
        "n_missed": int(n_episodes - n_detected) if n_episodes else 0,
        "episode_recall": recall,
        "median_lead_h": median_lead,
        "frac_lead_ge_3": frac_lead_ge_3,
        "median_alerts_per_detected": median_alerts,
        "origin_precision": float(n_tp / n_alerts) if n_alerts else float("nan"),
        "fp_origins": n_fp,
        "eligible_station_days": n_days,
        "fa_per_station_day": float(n_fp / n_days) if n_days else float("nan"),
        "station_days_with_fp": days_with_fp,
    }


def choose_operating_point(
    score: Sequence[float],
    frame: pd.DataFrame,
    grid: Sequence[float],
    fa_budget: float,
) -> dict[str, Any]:
    """Highest episode recall whose false alarms stay inside the budget.

    Ties prefer fewer false alarms, then a higher score cut. If every cut
    exceeds the budget, keep the cut with the fewest false alarms.
    """
    values = np.asarray(score, dtype=float)
    best_under = None
    best_under_key = None
    fallback = None
    fallback_key = None
    for threshold in grid:
        pred = (values >= float(threshold)).astype(int)
        metrics = episode_metrics(frame, pred)
        under_key = (
            metrics["episode_recall"] if np.isfinite(metrics["episode_recall"]) else -1.0,
            -metrics["fa_per_station_day"],
            float(threshold),
        )
        over_key = (
            -metrics["fa_per_station_day"],
            metrics["episode_recall"] if np.isfinite(metrics["episode_recall"]) else -1.0,
            float(threshold),
        )
        if metrics["fa_per_station_day"] <= fa_budget and (best_under_key is None or under_key > best_under_key):
            best_under_key = under_key
            best_under = (float(threshold), metrics)
        if fallback_key is None or over_key > fallback_key:
            fallback_key = over_key
            fallback = (float(threshold), metrics)
    chosen, metrics = best_under if best_under is not None else fallback
    return {
        "threshold": chosen,
        "budget_met": best_under is not None,
        "metrics": metrics,
    }


def clears_recall_margin(
    recall: float,
    baseline_recall: float,
    margin: float = RECALL_MARGIN,
) -> bool:
    if not np.isfinite(recall) or not np.isfinite(baseline_recall):
        return False
    return bool(recall >= baseline_recall + margin)


def fold_support(clears: Sequence[bool], required: int = FOLDS_REQUIRED) -> bool:
    return sum(bool(item) for item in clears) >= required
