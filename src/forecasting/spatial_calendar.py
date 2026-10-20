"""Leak-safe calendar and nearest-neighbor features for offline ablation.

These columns are not part of FEATURE_COLS_V2 and must not be written into the
model lock. Every spatial value is taken from PM2.5 at the forecast origin t
or earlier. Neighbor PM2.5 at t+1 is never read.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

def _daterange(start: date, end: date):
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


# Statutory Beijing heating is 15 Nov 00:00 through 15 Mar 24:00.
# Adjusted windows below follow municipal decisions inside the ML years.
# 2013-03-01..15 is only the tail of the 2012–13 season still inside the matrix.
HEATING_ADJUSTED: tuple[tuple[str, str], ...] = (
    ("2013-03-01 00:00:00", "2013-03-15 23:00:00"),
    ("2013-11-15 00:00:00", "2014-03-17 23:00:00"),  # +2 days (Beijing 供热会商)
    ("2014-11-15 00:00:00", "2015-03-15 23:00:00"),
    ("2015-11-15 00:00:00", "2016-03-15 23:00:00"),
    ("2016-11-13 00:00:00", "2017-03-15 23:00:00"),  # start brought forward to 13 Nov
)

# 正月初一 00:00 local — firework peak sits on this midnight (除夕 → 初一).
CNY_MIDNIGHTS: tuple[str, ...] = (
    "2013-02-10 00:00:00",
    "2014-01-31 00:00:00",
    "2015-02-19 00:00:00",
    "2016-02-08 00:00:00",
    "2017-01-28 00:00:00",
)
CNY_HOURS_WINDOW = 72

# 除夕 and 正月初一. The seven-day holiday is is_public_holiday, not this flag.
CNY_DATES: frozenset[date] = frozenset(
    {
        date(2013, 2, 9),
        date(2013, 2, 10),
        date(2014, 1, 30),
        date(2014, 1, 31),
        date(2015, 2, 18),
        date(2015, 2, 19),
        date(2016, 2, 7),
        date(2016, 2, 8),
        date(2017, 1, 27),
        date(2017, 1, 28),
    }
)

# Official rest days from State Council holiday notices (放假 / 补休 only).
PUBLIC_HOLIDAYS: frozenset[date] = frozenset(
    _d
    for start, end in (
        # 2013 国办发明电〔2012〕33号
        (date(2013, 1, 1), date(2013, 1, 3)),
        (date(2013, 2, 9), date(2013, 2, 15)),
        (date(2013, 4, 4), date(2013, 4, 6)),
        (date(2013, 4, 29), date(2013, 5, 1)),
        (date(2013, 6, 10), date(2013, 6, 12)),
        (date(2013, 9, 19), date(2013, 9, 21)),
        (date(2013, 10, 1), date(2013, 10, 7)),
        # 2014 国办发明电〔2013〕28号
        (date(2014, 1, 1), date(2014, 1, 1)),
        (date(2014, 1, 31), date(2014, 2, 6)),
        (date(2014, 4, 5), date(2014, 4, 5)),
        (date(2014, 4, 7), date(2014, 4, 7)),
        (date(2014, 5, 1), date(2014, 5, 3)),
        (date(2014, 6, 2), date(2014, 6, 2)),
        (date(2014, 9, 8), date(2014, 9, 8)),
        (date(2014, 10, 1), date(2014, 10, 7)),
        # 2015 国办发明电〔2014〕28号
        (date(2015, 1, 1), date(2015, 1, 3)),
        (date(2015, 2, 18), date(2015, 2, 24)),
        (date(2015, 4, 5), date(2015, 4, 6)),
        (date(2015, 5, 1), date(2015, 5, 1)),
        (date(2015, 6, 20), date(2015, 6, 20)),
        (date(2015, 6, 22), date(2015, 6, 22)),
        (date(2015, 9, 27), date(2015, 9, 27)),
        (date(2015, 10, 1), date(2015, 10, 7)),
        # 2016 国办发明电〔2015〕18号
        (date(2016, 1, 1), date(2016, 1, 1)),
        (date(2016, 2, 7), date(2016, 2, 13)),
        (date(2016, 4, 4), date(2016, 4, 4)),
        (date(2016, 5, 1), date(2016, 5, 2)),
        (date(2016, 6, 9), date(2016, 6, 11)),
        (date(2016, 9, 15), date(2016, 9, 17)),
        (date(2016, 10, 1), date(2016, 10, 7)),
    )
    for _d in _daterange(start, end)
)

# Weekend / weekday explicitly designated as a workday (上班).
MAKEUP_WORKDAYS: frozenset[date] = frozenset(
    {
        date(2013, 1, 5),
        date(2013, 1, 6),
        date(2013, 2, 16),
        date(2013, 2, 17),
        date(2013, 4, 7),
        date(2013, 4, 27),
        date(2013, 4, 28),
        date(2013, 6, 8),
        date(2013, 6, 9),
        date(2013, 9, 22),
        date(2013, 9, 29),
        date(2013, 10, 12),
        date(2014, 1, 26),
        date(2014, 2, 8),
        date(2014, 5, 4),
        date(2014, 9, 28),
        date(2014, 10, 11),
        date(2015, 1, 4),
        date(2015, 2, 15),
        date(2015, 2, 28),
        date(2015, 10, 10),
        date(2016, 2, 6),
        date(2016, 2, 14),
        date(2016, 6, 12),
        date(2016, 9, 18),
        date(2016, 10, 8),
        date(2016, 10, 9),
    }
)

CALENDAR_FEATURES: tuple[str, ...] = (
    "is_heating_season",
    "is_public_holiday",
    "is_chinese_new_year",
    "hours_from_cny_midnight",
    "is_makeup_workday",
)
SPATIAL_FEATURES: tuple[str, ...] = (
    "neighbor_pm25_lag1",
    "neighbor_pm25_lag3",
    "neighbor_pm25_mean",
    "spatial_gradient",
)
N_NEIGHBORS = 3


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlmb = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2.0) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2.0) ** 2
    return float(2.0 * radius * np.arcsin(np.sqrt(a)))


def statutory_heating_mask(times: pd.Series) -> pd.Series:
    """15 Nov 00:00 through 15 Mar 24:00, every year. Evaluation slice, not the feature."""
    ts = pd.to_datetime(times)
    month = ts.dt.month
    day = ts.dt.day
    return (
        ((month == 11) & (day >= 15))
        | (month == 12)
        | (month == 1)
        | (month == 2)
        | ((month == 3) & (day <= 15))
    )


def nearest_neighbor_table(stations: pd.DataFrame, *, n_neighbors: int = N_NEIGHBORS) -> pd.DataFrame:
    """Three nearest other stations, inverse-distance weights summing to 1."""
    frame = stations.loc[:, ["station_name", "latitude", "longitude"]].drop_duplicates("station_name")
    rows: list[dict[str, object]] = []
    records = frame.to_dict("records")
    for origin in records:
        dists: list[tuple[float, str]] = []
        for other in records:
            if other["station_name"] == origin["station_name"]:
                continue
            km = haversine_km(
                float(origin["latitude"]),
                float(origin["longitude"]),
                float(other["latitude"]),
                float(other["longitude"]),
            )
            dists.append((km, str(other["station_name"])))
        dists.sort()
        chosen = dists[:n_neighbors]
        inv = np.array([1.0 / km for km, _ in chosen], dtype=float)
        weights = inv / inv.sum()
        for rank, ((km, name), weight) in enumerate(zip(chosen, weights), start=1):
            rows.append(
                {
                    "station_name": origin["station_name"],
                    "neighbor_rank": rank,
                    "neighbor_name": name,
                    "distance_km": km,
                    "weight": float(weight),
                }
            )
    return pd.DataFrame(rows)


def _flag_dates(times: pd.Series, days: frozenset[date]) -> np.ndarray:
    py_dates = pd.to_datetime(times).dt.date
    return np.fromiter((1 if d in days else 0 for d in py_dates), dtype=np.int8, count=len(py_dates))


def _heating_flag(times: pd.Series) -> np.ndarray:
    ts = pd.to_datetime(times)
    flag = np.zeros(len(ts), dtype=np.int8)
    for start, end in HEATING_ADJUSTED:
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        flag[(ts >= start_ts) & (ts <= end_ts)] = 1
    return flag


def _hours_from_cny(times: pd.Series) -> np.ndarray:
    ts = pd.to_datetime(times).to_numpy(dtype="datetime64[ns]")
    midnights = np.array([np.datetime64(m) for m in CNY_MIDNIGHTS], dtype="datetime64[ns]")
    # Broadcast |t - midnight| and keep the nearest midnight inside the window.
    delta_hours = (ts[:, None] - midnights[None, :]).astype("timedelta64[ns]").astype(np.float64) / 3.6e12
    nearest = np.argmin(np.abs(delta_hours), axis=1)
    signed = delta_hours[np.arange(len(ts)), nearest]
    out = np.full(len(ts), np.nan, dtype=float)
    keep = np.abs(signed) <= CNY_HOURS_WINDOW
    out[keep] = signed[keep]
    return out


def add_calendar_features(df: pd.DataFrame, *, time_col: str = "event_time_local") -> pd.DataFrame:
    """Calendar flags known from the clock at origin t. No PM2.5 is read."""
    out = df.copy()
    times = out[time_col]
    out["is_heating_season"] = _heating_flag(times)
    out["is_public_holiday"] = _flag_dates(times, PUBLIC_HOLIDAYS)
    out["is_chinese_new_year"] = _flag_dates(times, CNY_DATES)
    out["hours_from_cny_midnight"] = _hours_from_cny(times)
    out["is_makeup_workday"] = _flag_dates(times, MAKEUP_WORKDAYS)
    return out


def _idw(values: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """Inverse-distance mean. Renormalize over neighbors that are finite at that hour."""
    mask = np.isfinite(values)
    w = np.where(mask, weights, 0.0)
    denom = w.sum(axis=1)
    numer = np.where(mask, values, 0.0)
    numer = (numer * w).sum(axis=1)
    out = np.full(len(values), np.nan, dtype=float)
    ok = denom > 0
    out[ok] = numer[ok] / denom[ok]
    return out


def add_spatial_features(
    df: pd.DataFrame,
    stations: pd.DataFrame,
    *,
    n_neighbors: int = N_NEIGHBORS,
    time_col: str = "event_time_local",
    pm_col: str = "pm25_ug_m3",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Neighbor PM2.5 at t, t−1h and t−3h for the three nearest stations.

    ``neighbor_pm25_mean`` is the inverse-distance mean at origin t.
    ``spatial_gradient`` is own PM2.5(t) minus that mean.
    Lags are clock lags on an hourly grid, not "previous non-null row".
    """
    if "station_name" not in df.columns:
        raise KeyError("add_spatial_features requires station_name")
    present = set(df["station_name"].astype(str))
    stations = stations[stations["station_name"].astype(str).isin(present)].copy()
    neighbors = nearest_neighbor_table(stations, n_neighbors=n_neighbors)
    name_to_key = (
        df.loc[:, ["station_name", "station_key"]]
        .drop_duplicates()
        .set_index("station_name")["station_key"]
        .to_dict()
    )
    panel = (
        df.loc[:, ["station_key", time_col, pm_col]]
        .drop_duplicates(["station_key", time_col], keep="last")
        .copy()
    )
    panel[time_col] = pd.to_datetime(panel[time_col])
    wide = panel.pivot(index=time_col, columns="station_key", values=pm_col).sort_index()
    full_idx = pd.date_range(wide.index.min(), wide.index.max(), freq="h")
    wide = wide.reindex(full_idx)

    out = df.copy().reset_index(drop=True)
    out[time_col] = pd.to_datetime(out[time_col])
    lag1 = np.full(len(out), np.nan)
    lag3 = np.full(len(out), np.nan)
    mean_t = np.full(len(out), np.nan)

    for station, sub in out.groupby("station_name", sort=False):
        idx = sub.index.to_numpy()
        sub_neighbors = neighbors[neighbors["station_name"] == station].sort_values("neighbor_rank")
        if sub_neighbors.empty:
            continue
        keys = [name_to_key[n] for n in sub_neighbors["neighbor_name"]]
        weights = sub_neighbors["weight"].to_numpy(dtype=float)
        pos = wide.index.get_indexer(pd.to_datetime(sub[time_col]))
        valid = pos >= 0

        def _lookup(shift: int, pos=pos, valid=valid, keys=keys, weights=weights) -> np.ndarray:
            take = pos.copy()
            take[valid] = pos[valid] - shift
            ok = valid & (take >= 0) & (take < len(wide))
            block = np.full((len(pos), len(keys)), np.nan)
            if ok.any():
                block[ok] = wide.iloc[take[ok]].loc[:, keys].to_numpy(dtype=float)
            return _idw(block, weights)

        lag1[idx] = _lookup(1)
        lag3[idx] = _lookup(3)
        mean_t[idx] = _lookup(0)

    out["neighbor_pm25_lag1"] = lag1
    out["neighbor_pm25_lag3"] = lag3
    out["neighbor_pm25_mean"] = mean_t
    out["spatial_gradient"] = out[pm_col].to_numpy(dtype=float) - mean_t
    return out, neighbors
