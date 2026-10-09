"""PM2.5 pollution episode detection (Phase 8c).

Rules (working):
- dirty hour: pm25_ug_m3 >= threshold; null is not dirty and breaks a run
- station episode: consecutive dirty hours with length >= min_hours
- multi-station: consecutive hours where count of stations in a qualifying episode >= K

Assumption: within each station, fact rows form a complete hourly timeline
(no missing calendar hours). Island ids use row adjacency = time adjacency.

Calendar fields on station episodes (`year`, `season`) are taken from the
**first hour** of the episode (start_time). Episodes that cross a year or
season boundary are attributed to the start only — intentional for reporting.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

from src.eda.db import read_sql

FIXED_THRESHOLDS = (75.0, 115.0)
MIN_HOURS_GRID = (1, 3, 6)
K_GRID = (3, 6, 9)


@dataclass(frozen=True)
class EpisodeRule:
    threshold_ug_m3: float
    min_hours: int
    multi_station_k: int
    threshold_label: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_hourly_frame() -> pd.DataFrame:
    """One station-hour row with PM2.5, weather, and calendar fields."""
    df = read_sql(
        """
        select
            fact.station_key,
            station.station_name,
            fact.event_time_local,
            fact.pm25_ug_m3,
            fact.temperature_c,
            fact.relative_humidity_pct,
            fact.wind_speed_m_s,
            fact.rain_mm,
            fact.cloud_cover_pct,
            calendar.year,
            calendar.season
        from dwh.fact_air_quality_hourly as fact
        inner join dwh.dim_station as station
            on fact.station_key = station.station_key
        inner join dwh.dim_date as calendar
            on fact.date_key = calendar.date_key
        order by fact.station_key, fact.event_time_local
        """
    )
    df["event_time_local"] = pd.to_datetime(df["event_time_local"])
    return df


def global_percentile_thresholds(df: pd.DataFrame) -> dict[str, float]:
    series = df["pm25_ug_m3"].dropna()
    return {
        "P90": float(series.quantile(0.90)),
        "P95": float(series.quantile(0.95)),
    }


def threshold_candidates(df: pd.DataFrame) -> list[tuple[str, float]]:
    pct = global_percentile_thresholds(df)
    out: list[tuple[str, float]] = [(f"{int(t)}", float(t)) for t in FIXED_THRESHOLDS]
    out.append((f"P90_{pct['P90']:.0f}", pct["P90"]))
    out.append((f"P95_{pct['P95']:.0f}", pct["P95"]))
    return out


def _island_ids(dirty: np.ndarray) -> np.ndarray:
    """Assign positive island ids to consecutive True runs; 0 elsewhere."""
    flags = np.asarray(dirty, dtype=bool)
    if flags.size == 0:
        return np.zeros(0, dtype=np.int64)
    starts = flags & np.concatenate(([True], ~flags[:-1]))
    return np.where(flags, np.cumsum(starts), 0).astype(np.int64)


def mark_in_episode(station_df: pd.DataFrame, threshold: float, min_hours: int) -> pd.Series:
    dirty = (station_df["pm25_ug_m3"].to_numpy(dtype=float) >= threshold) & station_df[
        "pm25_ug_m3"
    ].notna().to_numpy()
    island = _island_ids(dirty)
    in_episode = np.zeros(len(station_df), dtype=bool)
    if island.max() == 0:
        return pd.Series(in_episode, index=station_df.index)

    lengths = pd.Series(island[island > 0]).value_counts()
    keep = set(lengths[lengths >= min_hours].index.tolist())
    in_episode = np.isin(island, list(keep))
    return pd.Series(in_episode, index=station_df.index)


def detect_station_episodes(
    df: pd.DataFrame, threshold: float, min_hours: int
) -> pd.DataFrame:
    """Return one row per station episode."""
    rows: list[dict[str, Any]] = []
    for station_key, station_df in df.groupby("station_key", sort=False):
        station_df = station_df.sort_values("event_time_local")
        dirty = (station_df["pm25_ug_m3"].to_numpy(dtype=float) >= threshold) & station_df[
            "pm25_ug_m3"
        ].notna().to_numpy()
        island = _island_ids(dirty)
        if island.max() == 0:
            continue
        work = station_df.copy()
        work["_island"] = island
        work = work[work["_island"] > 0]
        for island_id, ep in work.groupby("_island", sort=True):
            duration = len(ep)
            if duration < min_hours:
                continue
            rows.append(
                {
                    "station_key": int(station_key),
                    "station_name": ep["station_name"].iloc[0],
                    "start_time": ep["event_time_local"].iloc[0],
                    "end_time": ep["event_time_local"].iloc[-1],
                    "duration_hours": int(duration),
                    "pm25_mean": float(ep["pm25_ug_m3"].mean()),
                    "pm25_max": float(ep["pm25_ug_m3"].max()),
                    "year": int(ep["year"].iloc[0]),
                    "season": ep["season"].iloc[0],
                    "temperature_c_avg": float(ep["temperature_c"].mean())
                    if ep["temperature_c"].notna().any()
                    else None,
                    "relative_humidity_pct_avg": float(ep["relative_humidity_pct"].mean())
                    if ep["relative_humidity_pct"].notna().any()
                    else None,
                    "wind_speed_m_s_avg": float(ep["wind_speed_m_s"].mean())
                    if ep["wind_speed_m_s"].notna().any()
                    else None,
                    "rain_mm_sum": float(ep["rain_mm"].fillna(0).sum()),
                    "cloud_cover_pct_avg": float(ep["cloud_cover_pct"].mean())
                    if ep["cloud_cover_pct"].notna().any()
                    else None,
                    "threshold_ug_m3": float(threshold),
                    "min_hours": int(min_hours),
                }
            )
    return pd.DataFrame(rows)


def hourly_station_counts(
    df: pd.DataFrame, threshold: float, min_hours: int
) -> pd.DataFrame:
    """Per timestamp: how many stations are inside a qualifying episode."""
    flags = []
    for _, station_df in df.groupby("station_key", sort=False):
        station_df = station_df.sort_values("event_time_local")
        marked = station_df[["event_time_local"]].copy()
        marked["in_episode"] = mark_in_episode(station_df, threshold, min_hours).to_numpy()
        flags.append(marked)
    all_flags = pd.concat(flags, ignore_index=True)
    counts = (
        all_flags.groupby("event_time_local", as_index=False)["in_episode"]
        .sum()
        .rename(columns={"in_episode": "n_stations_in_episode"})
    )
    counts["n_stations_in_episode"] = counts["n_stations_in_episode"].astype(int)
    return counts.sort_values("event_time_local")


def detect_multi_station_events(counts: pd.DataFrame, k: int) -> pd.DataFrame:
    """Runs of hours where n_stations_in_episode >= k."""
    active = counts["n_stations_in_episode"].to_numpy() >= k
    island = _island_ids(active)
    if island.max() == 0:
        return pd.DataFrame(
            columns=[
                "start_time",
                "end_time",
                "duration_hours",
                "peak_station_count",
                "mean_station_count",
                "k",
            ]
        )
    work = counts.copy()
    work["_island"] = island
    work = work[work["_island"] > 0]
    rows = []
    for _, ep in work.groupby("_island", sort=True):
        rows.append(
            {
                "start_time": ep["event_time_local"].iloc[0],
                "end_time": ep["event_time_local"].iloc[-1],
                "duration_hours": int(len(ep)),
                "peak_station_count": int(ep["n_stations_in_episode"].max()),
                "mean_station_count": float(ep["n_stations_in_episode"].mean()),
                "k": int(k),
            }
        )
    return pd.DataFrame(rows)


def summarize_station_episodes(episodes: pd.DataFrame) -> dict[str, Any]:
    if episodes.empty:
        return {
            "episode_count": 0,
            "stations_with_episodes": 0,
            "duration_median": None,
            "duration_p90": None,
            "duration_mean": None,
            "by_season": {},
            "by_year": {},
        }
    return {
        "episode_count": int(len(episodes)),
        "stations_with_episodes": int(episodes["station_name"].nunique()),
        "duration_median": float(episodes["duration_hours"].median()),
        "duration_p90": float(episodes["duration_hours"].quantile(0.9)),
        "duration_mean": float(episodes["duration_hours"].mean()),
        "by_season": episodes.groupby("season").size().astype(int).to_dict(),
        "by_year": {int(k): int(v) for k, v in episodes.groupby("year").size().items()},
    }


def sensitivity_grid(df: pd.DataFrame) -> pd.DataFrame:
    """threshold × min_hours summary (+ K=3 multi-station count as reference)."""
    rows: list[dict[str, Any]] = []
    for label, threshold in threshold_candidates(df):
        for min_hours in MIN_HOURS_GRID:
            episodes = detect_station_episodes(df, threshold, min_hours)
            summary = summarize_station_episodes(episodes)
            counts = hourly_station_counts(df, threshold, min_hours)
            multi_ref = {
                k: int(len(detect_multi_station_events(counts, k))) for k in K_GRID
            }
            hours_ge_k = {
                f"hours_ge_{k}": int((counts["n_stations_in_episode"] >= k).sum())
                for k in K_GRID
            }
            rows.append(
                {
                    "threshold_label": label,
                    "threshold_ug_m3": float(threshold),
                    "min_hours": int(min_hours),
                    **summary,
                    **{f"multi_events_k{k}": multi_ref[k] for k in K_GRID},
                    **hours_ge_k,
                    "pct_hours_any_episode": float(
                        100.0
                        * (counts["n_stations_in_episode"] > 0).mean()
                    ),
                }
            )
    return pd.DataFrame(rows)


def concurrent_distribution(
    df: pd.DataFrame, threshold: float, min_hours: int
) -> pd.DataFrame:
    counts = hourly_station_counts(df, threshold, min_hours)
    dist = (
        counts["n_stations_in_episode"]
        .value_counts()
        .sort_index()
        .rename_axis("n_stations")
        .reset_index(name="hour_count")
    )
    dist["pct"] = (100.0 * dist["hour_count"] / dist["hour_count"].sum()).round(2)
    return dist


def weather_episode_vs_baseline(
    df: pd.DataFrame, threshold: float, min_hours: int
) -> dict[str, Any]:
    """Compare weather inside qualifying episode hours vs other hours."""
    flags = []
    for _, station_df in df.groupby("station_key", sort=False):
        station_df = station_df.sort_values("event_time_local")
        part = station_df.copy()
        part["in_episode"] = mark_in_episode(station_df, threshold, min_hours).to_numpy()
        flags.append(part)
    marked = pd.concat(flags, ignore_index=True)
    inside = marked.loc[marked["in_episode"]]
    outside = marked.loc[~marked["in_episode"]]
    if inside.empty:
        return {"episode_hours": 0, "baseline_hours": int(len(outside))}

    def _avg(frame: pd.DataFrame, col: str) -> float | None:
        if frame.empty or frame[col].notna().sum() == 0:
            return None
        return float(frame[col].mean())

    return {
        "episode_hours": int(len(inside)),
        "baseline_hours": int(len(outside)),
        "episode": {
            "temperature_c_avg": _avg(inside, "temperature_c"),
            "relative_humidity_pct_avg": _avg(inside, "relative_humidity_pct"),
            "wind_speed_m_s_avg": _avg(inside, "wind_speed_m_s"),
            "rain_mm_mean": _avg(inside, "rain_mm"),
            "cloud_cover_pct_avg": _avg(inside, "cloud_cover_pct"),
            "pm25_ug_m3_avg": _avg(inside, "pm25_ug_m3"),
        },
        "baseline": {
            "temperature_c_avg": _avg(outside, "temperature_c"),
            "relative_humidity_pct_avg": _avg(outside, "relative_humidity_pct"),
            "wind_speed_m_s_avg": _avg(outside, "wind_speed_m_s"),
            "rain_mm_mean": _avg(outside, "rain_mm"),
            "cloud_cover_pct_avg": _avg(outside, "cloud_cover_pct"),
            "pm25_ug_m3_avg": _avg(outside, "pm25_ug_m3"),
        },
    }


def choose_locked_rule(concurrent_dist: pd.DataFrame) -> EpisodeRule:
    """Lock multi-station K given the preferred threshold / min_hours.

    Threshold (115) and min_hours (3) are fixed by Phase 8c policy — this
    helper only chooses ``multi_station_k`` from the concurrent distribution
    at that preferred rule (documented in episode_definition.md):

    - If pollution is highly spatially coherent (hours with n>=3 already common,
      and a large share of active hours are near network-wide), lock **K=6**
      (half of 12 stations) as the regional-event definition.
    - Else use the smallest K∈{3,6,9} with ≤~15% of all hours having n>=K.
    - Fallback K=3.
    """
    threshold = 115.0
    min_hours = 3
    total = float(concurrent_dist["hour_count"].sum()) or 1.0

    def _pct_ge(k: int) -> float:
        hours_ge = float(
            concurrent_dist.loc[concurrent_dist["n_stations"] >= k, "hour_count"].sum()
        )
        return 100.0 * hours_ge / total

    pct_ge_3 = _pct_ge(3)
    pct_ge_12 = _pct_ge(12)
    # Highly coherent network: many hours have ≥3 stations, and full-network
    # hours are a large slice of the calendar → K=6 is the meaningful "regional" cut.
    if pct_ge_3 > 15.0 and pct_ge_12 >= 5.0:
        chosen_k = 6
    else:
        chosen_k = 3
        for k in K_GRID:
            if _pct_ge(k) <= 15.0:
                chosen_k = k
                break

    return EpisodeRule(
        threshold_ug_m3=threshold,
        min_hours=min_hours,
        multi_station_k=chosen_k,
        threshold_label="115",
    )


def station_episode_stats(episodes: pd.DataFrame) -> pd.DataFrame:
    if episodes.empty:
        return pd.DataFrame()
    g = episodes.groupby("station_name", as_index=False).agg(
        episode_count=("duration_hours", "count"),
        duration_median=("duration_hours", "median"),
        duration_mean=("duration_hours", "mean"),
        duration_p90=("duration_hours", lambda s: s.quantile(0.9)),
        pm25_mean=("pm25_mean", "mean"),
        pm25_max=("pm25_max", "max"),
    )
    season = (
        episodes.groupby(["station_name", "season"]).size().unstack(fill_value=0)
    )
    season.columns = [f"episodes_{c}" for c in season.columns]
    out = g.merge(season.reset_index(), on="station_name", how="left")
    return out.sort_values("episode_count", ascending=False)
