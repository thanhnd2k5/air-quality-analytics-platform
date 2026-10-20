"""Upwind neighbor PM2.5. Formula fixed before any test-set look at M4.

Meteorological wind direction is the direction the wind comes FROM
(0° = north, 90° = east). A neighbor is upwind when the bearing from the
target to that neighbor matches this direction.

Weights use every other station, not the three nearest. Downwind stations
get weight 0. Wind slower than 1 m/s, or a missing direction, suppresses
the upwind concentration features. PM2.5 at t+1 is never read.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.forecasting.spatial_calendar import haversine_km

# Pre-registered. Not tuned on 2016-12-20.
UPWIND_WEAK_WIND_M_S = 1.0

UPWIND_FEATURES: tuple[str, ...] = (
    "upwind_pm25",
    "upwind_pm25_lag1",
    "upwind_minus_local",
    "upwind_unavailable",
    "upwind_weak_wind",
)


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing from point 1 to point 2, degrees clockwise from north."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dl = np.radians(lon2 - lon1)
    x = np.sin(dl) * np.cos(p2)
    y = np.cos(p1) * np.sin(p2) - np.sin(p1) * np.cos(p2) * np.cos(dl)
    return float((np.degrees(np.arctan2(x, y)) + 360.0) % 360.0)


def _weighted_mean(values: np.ndarray, weights: np.ndarray) -> np.ndarray:
    mask = np.isfinite(values) & np.isfinite(weights) & (weights > 0)
    w = np.where(mask, weights, 0.0)
    denom = w.sum(axis=1)
    numer = (np.where(mask, values, 0.0) * w).sum(axis=1)
    out = np.full(len(values), np.nan, dtype=float)
    ok = denom > 0
    out[ok] = numer[ok] / denom[ok]
    return out


def _geometry(stations: pd.DataFrame) -> dict[str, dict[str, np.ndarray]]:
    frame = stations.loc[:, ["station_name", "latitude", "longitude"]].drop_duplicates("station_name")
    records = frame.to_dict("records")
    out: dict[str, dict[str, np.ndarray]] = {}
    for origin in records:
        names, dist, bear = [], [], []
        for other in records:
            if other["station_name"] == origin["station_name"]:
                continue
            names.append(str(other["station_name"]))
            dist.append(
                haversine_km(
                    float(origin["latitude"]),
                    float(origin["longitude"]),
                    float(other["latitude"]),
                    float(other["longitude"]),
                )
            )
            bear.append(
                bearing_deg(
                    float(origin["latitude"]),
                    float(origin["longitude"]),
                    float(other["latitude"]),
                    float(other["longitude"]),
                )
            )
        out[str(origin["station_name"])] = {
            "names": np.array(names, dtype=object),
            "distance_km": np.asarray(dist, dtype=float),
            "bearing_deg": np.asarray(bear, dtype=float),
        }
    return out


def _alignment_weights(
    bearing: np.ndarray,
    azimuth: np.ndarray,
    speed: np.ndarray,
    distance_km: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (n, n_neighbors) weights and a weak-wind mask. Downwind weight is 0."""
    az = np.asarray(azimuth, dtype=float)
    spd = np.asarray(speed, dtype=float)
    weak = ~np.isfinite(spd) | (spd < UPWIND_WEAK_WIND_M_S)
    delta = bearing[None, :] - az[:, None]
    align = np.cos(np.radians(delta))
    align = np.where(np.isfinite(az)[:, None], align, np.nan)
    weights = np.clip(align, 0.0, None) / distance_km[None, :]
    weights = np.where(np.isfinite(weights), weights, 0.0)
    weights[weak] = 0.0
    return weights, weak


def add_upwind_features(
    df: pd.DataFrame,
    stations: pd.DataFrame,
    wind: pd.DataFrame,
    *,
    time_col: str = "event_time_local",
    pm_col: str = "pm25_ug_m3",
    speed_col: str = "wind_speed_m_s",
) -> pd.DataFrame:
    """
    Upwind PM2.5 at t and t−1h, plus missing/weak flags.

    ``wind`` supplies ``azimuth_deg`` (meteorological, degrees). Wind speed
    is taken from ``df`` when present, else from ``wind``.
    """
    if "station_name" not in df.columns:
        raise KeyError("add_upwind_features requires station_name")
    out = df.copy().reset_index(drop=True)
    out[time_col] = pd.to_datetime(out[time_col])
    present = set(out["station_name"].astype(str))
    stations = stations[stations["station_name"].astype(str).isin(present)].copy()
    geo = _geometry(stations)

    wx = wind.loc[:, ["station_name", time_col, "azimuth_deg"]].copy()
    wx[time_col] = pd.to_datetime(wx[time_col])
    wx = wx.drop_duplicates(["station_name", time_col], keep="last")
    if speed_col not in out.columns:
        if speed_col not in wind.columns:
            raise KeyError(f"Missing {speed_col}")
        extra = wind.loc[:, ["station_name", time_col, speed_col]].copy()
        extra[time_col] = pd.to_datetime(extra[time_col])
        out = out.merge(extra, on=["station_name", time_col], how="left")
    out = out.merge(wx, on=["station_name", time_col], how="left")

    name_to_key = (
        out.loc[:, ["station_name", "station_key"]].drop_duplicates().set_index("station_name")["station_key"].to_dict()
    )
    panel = (
        out.loc[:, ["station_key", time_col, pm_col]]
        .drop_duplicates(["station_key", time_col], keep="last")
        .copy()
    )
    wide_pm = panel.pivot(index=time_col, columns="station_key", values=pm_col).sort_index()
    full_idx = pd.date_range(wide_pm.index.min(), wide_pm.index.max(), freq="h")
    wide_pm = wide_pm.reindex(full_idx)

    upwind_t = np.full(len(out), np.nan)
    upwind_lag = np.full(len(out), np.nan)
    unavailable = np.zeros(len(out), dtype=np.int8)
    weak_flag = np.zeros(len(out), dtype=np.int8)

    for station, sub in out.groupby("station_name", sort=False):
        spec = geo.get(str(station))
        if spec is None:
            continue
        idx = sub.index.to_numpy()
        names = spec["names"]
        keys = [name_to_key[n] for n in names if n in name_to_key]
        if len(keys) != len(names):
            keep = [i for i, n in enumerate(names) if n in name_to_key]
            names = names[keep]
            keys = [name_to_key[n] for n in names]
            distance = spec["distance_km"][keep]
            bearing = spec["bearing_deg"][keep]
        else:
            distance = spec["distance_km"]
            bearing = spec["bearing_deg"]
        pos = wide_pm.index.get_indexer(pd.to_datetime(sub[time_col]))
        valid = pos >= 0

        def _pm_at(shift: int) -> np.ndarray:
            take = pos.copy()
            take[valid] = pos[valid] - shift
            ok = valid & (take >= 0) & (take < len(wide_pm))
            block = np.full((len(pos), len(keys)), np.nan)
            if ok.any():
                block[ok] = wide_pm.iloc[take[ok]].loc[:, keys].to_numpy(dtype=float)
            return block

        pm_t = _pm_at(0)
        pm_lag = _pm_at(1)
        az_t = sub["azimuth_deg"].to_numpy(dtype=float)
        spd_t = sub[speed_col].to_numpy(dtype=float)
        # Wind at t−1 from the same station column, clock-aligned via the row order
        # of this station only when rows are hourly and sorted. Use the wide clock.
        az_series = (
            out.loc[out["station_name"].eq(station), [time_col, "azimuth_deg", speed_col]]
            .drop_duplicates(time_col)
            .set_index(time_col)
            .sort_index()
        )
        az_wide = az_series.reindex(full_idx)
        def _wx_at(shift: int, col: str) -> np.ndarray:
            take = pos.copy()
            take[valid] = pos[valid] - shift
            ok = valid & (take >= 0) & (take < len(full_idx))
            values = np.full(len(pos), np.nan)
            if ok.any():
                values[ok] = az_wide.iloc[take[ok]][col].to_numpy(dtype=float)
            return values

        w_t, weak_t = _alignment_weights(bearing, az_t, spd_t, distance)
        w_lag, _ = _alignment_weights(bearing, _wx_at(1, "azimuth_deg"), _wx_at(1, speed_col), distance)
        mean_t = _weighted_mean(pm_t, w_t)
        mean_lag = _weighted_mean(pm_lag, w_lag)
        # Geometry flag ignores the weak-wind suppression: unavailable means
        # the direction is missing or no neighbor with data sits upwind.
        forced_speed = np.where(
            np.isfinite(spd_t),
            np.maximum(spd_t, UPWIND_WEAK_WIND_M_S),
            UPWIND_WEAK_WIND_M_S,
        )
        w_geom, _ = _alignment_weights(bearing, az_t, forced_speed, distance)
        geom_mean = _weighted_mean(pm_t, w_geom)
        upwind_t[idx] = mean_t
        upwind_lag[idx] = mean_lag
        weak_flag[idx] = weak_t.astype(np.int8)
        unavailable[idx] = (~np.isfinite(az_t) | ~np.isfinite(geom_mean)).astype(np.int8)

    out["upwind_pm25"] = upwind_t
    out["upwind_pm25_lag1"] = upwind_lag
    out["upwind_minus_local"] = upwind_t - out[pm_col].to_numpy(dtype=float)
    out["upwind_unavailable"] = unavailable
    out["upwind_weak_wind"] = weak_flag
    out = out.drop(columns=["azimuth_deg"])
    return out
