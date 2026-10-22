"""Station profiles fit on one time window.

Pollutant statistics use only hours inside the window. Episode statistics
default to the same hours, so a run that continues past the cutoff is not
given those later hours. The published cluster remains the EDA assignment.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.clustering.fit import (
    agreement_rate,
    assignment_frame,
    choose_lock_k,
    fit_kmeans,
    kmeans_metrics,
    prepare_matrix,
)
from src.clustering.profiles import CLUSTER_FEATURE_COLS, META_COLS
from src.forecasting.constants import EPISODE_MIN_HOURS, EPISODE_THRESHOLD

POLLUTANT_MEAN_COLS = (
    ("pm10_ug_m3", "mean_pm10"),
    ("no2_ug_m3", "mean_no2"),
    ("co_ug_m3", "mean_co"),
    ("so2_ug_m3", "mean_so2"),
    ("o3_ug_m3", "mean_o3"),
)
SEASON_MONTHS = {
    "winter": (12, 1, 2),
    "spring": (3, 4, 5),
    "summer": (6, 7, 8),
    "autumn": (9, 10, 11),
}


def meteorological_season(month: pd.Series) -> pd.Series:
    """Same season labels as ``dwh.dim_date``: winter Dec–Feb through autumn Sep–Nov."""
    m = month.astype(int)
    season = pd.Series("autumn", index=m.index, dtype="string")
    season.loc[m.isin(SEASON_MONTHS["winter"])] = "winter"
    season.loc[m.isin(SEASON_MONTHS["spring"])] = "spring"
    season.loc[m.isin(SEASON_MONTHS["summer"])] = "summer"
    return season


def _island_ids(dirty: np.ndarray, times: np.ndarray) -> np.ndarray:
    """Consecutive dirty hours. A gap other than one hour starts a new run."""
    flags = np.asarray(dirty, dtype=bool)
    island = np.zeros(len(flags), dtype=np.int64)
    current = 0
    previous_on = False
    previous_time = None
    for i, flag in enumerate(flags):
        adjacent = False
        if previous_time is not None:
            adjacent = (times[i] - previous_time) / np.timedelta64(1, "s") == 3600
        if flag and previous_on and adjacent:
            island[i] = current
        elif flag:
            current += 1
            island[i] = current
            previous_on = True
        else:
            previous_on = False
        previous_time = times[i]
    return island


def episode_runs(
    hourly: pd.DataFrame,
    *,
    threshold: float = EPISODE_THRESHOLD,
    min_hours: int = EPISODE_MIN_HOURS,
) -> pd.DataFrame:
    """One row per station episode. Null PM2.5 breaks a run."""
    rows: list[dict[str, Any]] = []
    for station_key, station_df in hourly.groupby("station_key", sort=False):
        ordered = station_df.sort_values("event_time_local")
        pm25 = ordered["pm25_ug_m3"].to_numpy(dtype=float)
        times = pd.to_datetime(ordered["event_time_local"]).to_numpy()
        dirty = np.isfinite(pm25) & (pm25 >= threshold)
        island = _island_ids(dirty, times)
        if island.max() == 0:
            continue
        work = ordered.copy()
        work["_island"] = island
        work = work.loc[work["_island"] > 0]
        for _, episode in work.groupby("_island", sort=True):
            duration = int(len(episode))
            if duration < min_hours:
                continue
            rows.append(
                {
                    "station_key": int(station_key),
                    "start_time": pd.Timestamp(episode["event_time_local"].iloc[0]),
                    "duration_hours": duration,
                }
            )
    if not rows:
        return pd.DataFrame(columns=["station_key", "start_time", "duration_hours"])
    return pd.DataFrame(rows)


def _round4(series: pd.Series) -> float:
    if series.dropna().empty:
        return float("nan")
    return float(np.round(series.mean(), 4))


def station_profiles(
    hourly: pd.DataFrame,
    *,
    window_start: str,
    window_end: str,
    episode_mode: str = "inside",
) -> pd.DataFrame:
    """One row per station. ``episode_mode='inside'`` ignores hours after the cutoff.

    ``episode_mode='start_in_window'`` detects episodes on the whole frame and
    keeps those whose start falls inside the window. That matches the published
    profile SQL, which can count hours after the window when a run continues.
    """
    if episode_mode not in {"inside", "start_in_window"}:
        raise ValueError("episode_mode must be 'inside' or 'start_in_window'")
    frame = hourly.copy()
    frame["event_time_local"] = pd.to_datetime(frame["event_time_local"])
    start = pd.Timestamp(window_start)
    end = pd.Timestamp(window_end)
    inside = frame.loc[
        (frame["event_time_local"] >= start) & (frame["event_time_local"] <= end)
    ].copy()
    if inside.empty:
        raise ValueError("no hours inside the profile window")
    inside["season"] = meteorological_season(inside["event_time_local"].dt.month)

    if episode_mode == "inside":
        episodes = episode_runs(inside)
    else:
        episodes = episode_runs(frame)
        episodes = episodes.loc[
            (episodes["start_time"] >= start) & (episodes["start_time"] <= end)
        ]

    rows: list[dict[str, Any]] = []
    for station_key, station_df in inside.groupby("station_key", sort=False):
        pm25 = station_df["pm25_ug_m3"]
        observed = pm25.dropna()
        row: dict[str, Any] = {
            "station_key": int(station_key),
            "station_name": str(station_df["station_name"].iloc[0]),
            "district": str(station_df["district"].iloc[0]),
            "hour_count": int(len(station_df)),
            "pm25_hour_count": int(observed.shape[0]),
            "mean_pm25": _round4(observed),
            "median_pm25": float(np.round(observed.median(), 4)) if len(observed) else float("nan"),
            "std_pm25": float(np.round(observed.std(ddof=1), 4)) if len(observed) > 1 else float("nan"),
            "pct_hours_pm25_ge_75": _pct(observed, 75.0),
            "pct_hours_pm25_ge_115": _pct(observed, EPISODE_THRESHOLD),
        }
        for source, name in POLLUTANT_MEAN_COLS:
            row[name] = _round4(station_df[source])
        for season in ("spring", "summer", "autumn", "winter"):
            row[f"mean_pm25_{season}"] = _round4(station_df.loc[station_df["season"] == season, "pm25_ug_m3"])
        station_episodes = episodes.loc[episodes["station_key"] == int(station_key)]
        if station_episodes.empty:
            row["episode_count"] = 0
            row["mean_episode_duration_h"] = 0.0
            row["total_episode_hours"] = 0
        else:
            row["episode_count"] = int(len(station_episodes))
            row["mean_episode_duration_h"] = float(np.round(station_episodes["duration_hours"].mean(), 4))
            row["total_episode_hours"] = int(station_episodes["duration_hours"].sum())
        rows.append(row)
    profiles = pd.DataFrame(rows)
    ordered = [c for c in list(META_COLS) + list(CLUSTER_FEATURE_COLS) if c in profiles.columns]
    return profiles[ordered].sort_values("station_key").reset_index(drop=True)


def _pct(observed: pd.Series, threshold: float) -> float:
    if observed.empty:
        return float("nan")
    return float(np.round(100.0 * float((observed >= threshold).sum()) / len(observed), 4))


def fit_window_clusters(profiles: pd.DataFrame, *, k: int = 2) -> dict[str, Any]:
    """KMeans at a fixed k. The scaler is fit on this profile matrix only."""
    matrix = prepare_matrix(profiles)
    metrics = kmeans_metrics(matrix.X)
    labels = fit_kmeans(matrix.X, k)
    assignment = assignment_frame(matrix, labels, method="kmeans", k=k)
    return {
        "k": k,
        "k_by_silhouette": choose_lock_k(metrics),
        "metrics": metrics,
        "assignment": assignment,
    }


def assignment_agreement(left: pd.DataFrame, right: pd.DataFrame) -> dict[str, Any]:
    """Pairwise co-membership, plus stations that move after matching labels by overlap."""
    merged = left.merge(right, on="station_key", suffixes=("_left", "_right"))
    if merged.empty:
        raise ValueError("assignments share no station_key")
    left_labels = merged["cluster_id_left"].to_numpy()
    right_labels = merged["cluster_id_right"].to_numpy()
    moved = _moved_stations(merged)
    return {
        "n_stations": int(len(merged)),
        "pairwise_agreement": float(agreement_rate(left_labels, right_labels)),
        "n_moved": int(len(moved)),
        "moved_stations": moved,
    }


def _moved_stations(merged: pd.DataFrame) -> list[str]:
    """Stations whose cluster does not match the best overlap with the left labels."""
    mapping: dict[int, int] = {}
    remaining = set(int(v) for v in merged["cluster_id_right"].unique())
    for left_id, group in merged.groupby("cluster_id_left"):
        counts = group["cluster_id_right"].value_counts()
        for candidate, _ in counts.items():
            candidate = int(candidate)
            if candidate in remaining:
                mapping[int(left_id)] = candidate
                remaining.remove(candidate)
                break
    name_col = "station_name_left" if "station_name_left" in merged.columns else "station_name"
    moved: list[str] = []
    for _, row in merged.iterrows():
        expected = mapping.get(int(row["cluster_id_left"]))
        if expected is None or int(row["cluster_id_right"]) != expected:
            moved.append(str(row[name_col]))
    return sorted(moved)
