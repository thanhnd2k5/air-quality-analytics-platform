"""Offline spatial data-quality scores. Does not impute or alter PM2.5.

The suspect flag is a review mark. A flagged hour keeps its original value.
The rule has no calendar date in it. Cuts were frozen from the train split:
at a context of at least 50 µg/m³ the train 99.9th percentile of isolation is
0.333, and isolation of 0.5 is where that train tail's median PM2.5 sits on
the reporting floor while the median gap stays above 50 µg/m³. Validation
was not used to move the cuts.

``suspect_spatiotemporal`` uses the previous and the next hour, so it is an
offline review flag. ``suspect_spatiotemporal_causal`` uses only the previous
hour and the same-hour neighbors, which is what a forecast at t can see.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.forecasting.spatial_calendar import N_NEIGHBORS, nearest_neighbor_table

CONTEXT_MIN_UG = 50.0
ISOLATION_MIN = 0.5
MIN_SPATIAL_NEIGHBORS = 2
PM10_CONTEXT_MIN_UG = 50.0
PM10_DISAGREE_RATIO = 0.25
CO_ELEVATED_UG = 2600.0


@dataclass(frozen=True)
class SpatialQualityRule:
    """Numeric cuts. Defaults are the train-frozen review rule."""

    context_min_ug: float = CONTEXT_MIN_UG
    isolation_min: float = ISOLATION_MIN
    min_spatial_neighbors: int = MIN_SPATIAL_NEIGHBORS
    pm10_context_min_ug: float = PM10_CONTEXT_MIN_UG
    pm10_disagree_ratio: float = PM10_DISAGREE_RATIO
    co_elevated_ug: float = CO_ELEVATED_UG


FROZEN_RULE = SpatialQualityRule()


def _as_float(series: pd.Series) -> np.ndarray:
    return pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)


def _nanmedian_rows(block: np.ndarray, min_count: int) -> np.ndarray:
    finite = np.isfinite(block)
    count = finite.sum(axis=1)
    out = np.full(len(block), np.nan, dtype=float)
    for n_obs in range(min_count, block.shape[1] + 1):
        sel = count == n_obs
        if not sel.any():
            continue
        out[sel] = np.nanmedian(block[sel], axis=1)
    return out


def aggregate_neighbors(values: np.ndarray, weights: np.ndarray) -> dict[str, float]:
    """IDW mean, unweighted mean, median, and a one-point trimmed mean.

    With three finite neighbors, symmetric trimming of both extremes leaves
    the middle value, which is the median. The trimmed mean used here drops
    only the neighbor farthest from the median, then averages the other two.
    Fewer than three finite neighbors cannot drop a point, so the trimmed
    mean equals the unweighted mean. No value is imputed.
    """
    values = np.asarray(values, dtype=float).reshape(-1)
    weights = np.asarray(weights, dtype=float).reshape(-1)
    if values.shape != weights.shape:
        raise ValueError("values and weights must have the same length")
    finite = np.isfinite(values) & np.isfinite(weights) & (weights > 0)
    empty = {
        "idw_mean": np.nan,
        "mean": np.nan,
        "median": np.nan,
        "trimmed_mean": np.nan,
        "n_finite": 0,
    }
    if not finite.any():
        return empty
    observed = values[finite]
    used_weights = weights[finite]
    idw = float(np.dot(used_weights, observed) / used_weights.sum())
    mean = float(observed.mean())
    median = float(np.median(observed))
    if len(observed) >= 3:
        drop = int(np.argmax(np.abs(observed - median)))
        trimmed = float(np.delete(observed, drop).mean())
    else:
        trimmed = mean
    return {
        "idw_mean": idw,
        "mean": mean,
        "median": median,
        "trimmed_mean": trimmed,
        "n_finite": int(len(observed)),
    }


def _row_aggregates(block: np.ndarray, weights: np.ndarray) -> dict[str, np.ndarray]:
    finite = np.isfinite(block)
    weight_row = np.broadcast_to(weights, block.shape)
    used = np.where(finite, weight_row, 0.0)
    denom = used.sum(axis=1)
    count = finite.sum(axis=1)
    observed = np.where(finite, block, 0.0)
    idw = np.full(len(block), np.nan, dtype=float)
    mean = np.full(len(block), np.nan, dtype=float)
    ok = denom > 0
    idw[ok] = (observed * used).sum(axis=1)[ok] / denom[ok]
    mean[ok] = observed.sum(axis=1)[ok] / count[ok]
    median = _nanmedian_rows(block, min_count=1)
    trimmed = mean.copy()
    three = count >= 3
    if three.any():
        chosen = block[three]
        distance = np.abs(chosen - median[three, None])
        drop = np.argmax(distance, axis=1)
        keep = np.ones(chosen.shape, dtype=bool)
        keep[np.arange(len(chosen)), drop] = False
        trimmed[three] = chosen[keep].reshape(len(chosen), chosen.shape[1] - 1).mean(axis=1)
    return {
        "idw_mean": idw,
        "mean": mean,
        "median": median,
        "trimmed_mean": trimmed,
        "n_finite": count.astype(int),
    }


def _pm10_context(pm25: np.ndarray, pm10: np.ndarray, rule: SpatialQualityRule) -> np.ndarray:
    labels = np.full(len(pm25), "pm10_missing", dtype=object)
    finite = np.isfinite(pm25) & np.isfinite(pm10)
    ratio = np.full(len(pm25), np.nan, dtype=float)
    nonzero = finite & (pm10 != 0)
    ratio[nonzero] = pm25[nonzero] / pm10[nonzero]
    disagrees = finite & (pm10 >= rule.pm10_context_min_ug) & (ratio <= rule.pm10_disagree_ratio)
    also_low = finite & (pm10 < rule.pm10_context_min_ug)
    consistent = finite & ~disagrees & ~also_low
    labels[also_low] = "pm10_also_low"
    labels[disagrees] = "pm10_disagrees"
    labels[consistent] = "pm10_consistent"
    return labels


def _clock_shift(pm: pd.Series, times: pd.Series, hours: int) -> np.ndarray:
    series = pd.Series(_as_float(pm), index=pd.to_datetime(times))
    if not series.index.is_unique:
        raise ValueError("station hours must be unique before scoring")
    shifted = times + pd.Timedelta(hours=hours)
    return series.reindex(pd.to_datetime(shifted)).to_numpy(dtype=float)


def score_spatial_quality(
    panel: pd.DataFrame,
    stations: pd.DataFrame,
    *,
    rule: SpatialQualityRule | None = None,
    n_neighbors: int = N_NEIGHBORS,
    time_col: str = "event_time_local",
    pm_col: str = "pm25_ug_m3",
) -> pd.DataFrame:
    """Score each station-hour. The PM2.5 column is copied through unchanged."""
    rule = rule or FROZEN_RULE
    required = {"station_name", time_col, pm_col}
    missing = required - set(panel.columns)
    if missing:
        raise KeyError(f"score_spatial_quality requires {sorted(missing)}")
    if panel.duplicated(["station_name", time_col]).any():
        raise ValueError("Duplicate station_name + event time")

    working = panel.copy()
    working[time_col] = pd.to_datetime(working[time_col])
    working[pm_col] = pd.to_numeric(working[pm_col], errors="coerce")
    present = set(working["station_name"].astype(str))
    station_frame = stations[stations["station_name"].astype(str).isin(present)].copy()
    neighbors = nearest_neighbor_table(station_frame, n_neighbors=n_neighbors)
    wide = (
        working.loc[:, ["station_name", time_col, pm_col]]
        .drop_duplicates(["station_name", time_col], keep="last")
        .pivot(index=time_col, columns="station_name", values=pm_col)
        .sort_index()
    )

    pieces: list[pd.DataFrame] = []
    for station, sub in working.groupby("station_name", sort=False):
        sub = sub.sort_values(time_col)
        times = pd.to_datetime(sub[time_col])
        pm = _as_float(sub[pm_col])
        lag = _clock_shift(sub[pm_col], times, -1)
        lead = _clock_shift(sub[pm_col], times, 1)
        station_neighbors = neighbors[neighbors["station_name"] == station].sort_values("neighbor_rank")
        names = [str(name) for name in station_neighbors["neighbor_name"]]
        weights = station_neighbors["weight"].to_numpy(dtype=float)
        block = np.full((len(sub), n_neighbors), np.nan, dtype=float)
        for col, name in enumerate(names):
            if name in wide.columns:
                block[:, col] = wide[name].reindex(times).to_numpy(dtype=float)
        while len(names) < n_neighbors:
            names.append("")
            weights = np.append(weights, np.nan)

        aggregates = _row_aggregates(block, weights[:n_neighbors])
        spatial = _nanmedian_rows(block, rule.min_spatial_neighbors)
        both = np.isfinite(lag) & np.isfinite(lead) & np.isfinite(pm)
        temporal_floor = np.where(both, np.minimum(lag, lead), np.nan)
        temporal_ok = both & (temporal_floor > 0)
        spatial_ok = np.isfinite(spatial) & (spatial > 0)
        temporal_deficit = np.full(len(sub), np.nan, dtype=float)
        spatial_deficit = np.full(len(sub), np.nan, dtype=float)
        temporal_deficit[temporal_ok] = (temporal_floor[temporal_ok] - pm[temporal_ok]) / temporal_floor[temporal_ok]
        spatial_deficit[spatial_ok] = (spatial[spatial_ok] - pm[spatial_ok]) / spatial[spatial_ok]
        isolation = np.minimum(temporal_deficit, spatial_deficit)
        context = np.minimum(temporal_floor, spatial)
        suspect = (
            temporal_ok
            & spatial_ok
            & np.isfinite(context)
            & (context >= rule.context_min_ug)
            & np.isfinite(isolation)
            & (isolation >= rule.isolation_min)
        )

        lag_ok = np.isfinite(lag) & np.isfinite(pm) & (lag > 0) & spatial_ok
        causal_context = np.minimum(lag, spatial)
        causal_isolation = np.full(len(sub), np.nan, dtype=float)
        causal_isolation[lag_ok] = np.minimum(
            (lag[lag_ok] - pm[lag_ok]) / lag[lag_ok],
            spatial_deficit[lag_ok],
        )
        suspect_causal = (
            lag_ok
            & np.isfinite(causal_context)
            & (causal_context >= rule.context_min_ug)
            & np.isfinite(causal_isolation)
            & (causal_isolation >= rule.isolation_min)
        )

        pm10 = _as_float(sub["pm10_ug_m3"]) if "pm10_ug_m3" in sub.columns else np.full(len(sub), np.nan)
        co = _as_float(sub["co_ug_m3"]) if "co_ug_m3" in sub.columns else np.full(len(sub), np.nan)
        no2 = _as_float(sub["no2_ug_m3"]) if "no2_ug_m3" in sub.columns else np.full(len(sub), np.nan)
        scored = sub.copy()
        scored[pm_col] = pm
        scored["pm25_lag1h"] = lag
        scored["pm25_lead1h"] = lead
        scored["temporal_floor_ug"] = temporal_floor
        scored["spatial_median_ug"] = spatial
        scored["context_ug"] = np.where(temporal_ok & spatial_ok, context, np.nan)
        scored["isolation"] = isolation
        scored["suspect_spatiotemporal"] = suspect
        scored["isolation_causal"] = causal_isolation
        scored["suspect_spatiotemporal_causal"] = suspect_causal
        scored["pm10_context"] = _pm10_context(pm, pm10, rule)
        scored["co_elevated"] = np.isfinite(co) & (co >= rule.co_elevated_ug)
        scored["neighbor_idw_mean"] = aggregates["idw_mean"]
        scored["neighbor_mean"] = aggregates["mean"]
        scored["neighbor_median"] = aggregates["median"]
        scored["neighbor_trimmed_mean"] = aggregates["trimmed_mean"]
        scored["neighbor_n_finite"] = aggregates["n_finite"]
        for rank in range(n_neighbors):
            scored[f"neighbor_{rank + 1}_name"] = names[rank]
            scored[f"neighbor_{rank + 1}_pm25"] = block[:, rank]
            scored[f"neighbor_{rank + 1}_weight"] = weights[rank]
        pieces.append(scored)

    return pd.concat(pieces, ignore_index=True)


def attach_suspect_neighbor_influence(
    scored: pd.DataFrame,
    *,
    n_neighbors: int = N_NEIGHBORS,
    time_col: str = "event_time_local",
) -> pd.DataFrame:
    """Recompute neighbor IDW with suspect neighbor hours left out.

    The original PM2.5 column is not rewritten. The excluding aggregate is a
    sensitivity column only: a suspect neighbor is treated as unavailable for
    that counterfactual, not replaced with another concentration.
    """
    out = scored.copy()
    out[time_col] = pd.to_datetime(out[time_col])
    lookup = out.assign(station_name=out["station_name"].astype(str)).set_index(
        ["station_name", time_col]
    )["suspect_spatiotemporal"]
    if not lookup.index.is_unique:
        raise ValueError("station_name + event time must be unique")
    values = []
    weights = []
    suspect_cols = []
    for rank in range(1, n_neighbors + 1):
        name_col = f"neighbor_{rank}_name"
        keys = pd.MultiIndex.from_arrays([out[name_col].astype(str), out[time_col]])
        flag = lookup.reindex(keys).fillna(False).to_numpy(dtype=bool)
        out[f"neighbor_{rank}_suspect"] = flag
        values.append(out[f"neighbor_{rank}_pm25"].to_numpy(dtype=float))
        weights.append(out[f"neighbor_{rank}_weight"].to_numpy(dtype=float))
        suspect_cols.append(flag)
    block = np.column_stack(values)
    weight_row = np.column_stack(weights)
    suspect = np.column_stack(suspect_cols)
    excluded = _row_aggregates(np.where(suspect, np.nan, block), weight_row)
    out["neighbor_suspect_count"] = suspect.sum(axis=1).astype(int)
    out["neighbor_idw_excluding_suspect"] = excluded["idw_mean"]
    out["neighbor_mean_excluding_suspect"] = excluded["mean"]
    out["neighbor_median_excluding_suspect"] = excluded["median"]
    out["neighbor_trimmed_excluding_suspect"] = excluded["trimmed_mean"]
    return out
