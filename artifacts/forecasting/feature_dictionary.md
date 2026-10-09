# Phase 10b – Forecast feature dictionary

Target: **`y_pm25_tplus1`** = PM2.5 at station hour **t+1**, using only information available at **t**.

## Split (locked)

| Split | Window |
|-------|--------|
| train | 2013-03-01 → 2015-12-31 |
| val | 2016-01-01 → 2016-06-30 |
| test | 2016-07-01 → 2016-12-31 |

2017 excluded from primary eval.

## Meta (not model inputs as-is)

| Column | Notes |
|--------|-------|
| `station_key` | Also used as a feature (integer id / later one-hot in Linear) |
| `event_time_local` | Prediction origin time t |
| `target_time_local` | t+1 |
| `split` | train / val / test |
| `cluster_label` | Human label; model uses `cluster_id` |
| `pm25_ug_m3` | Observed at t (equals `pm25_lag_1` of next row; kept for baseline) |
| `season` | String; model uses `season_code` |

## Features (v1)

| Feature | Construction | Leakage note |
|---------|----------------|--------------|
| `hour` | `time_key` at t | OK |
| `month`, `day_of_week`, `season_code` | from `dim_date` at t | OK |
| `station_key`, `cluster_id` | station + Phase 9 mart | time-invariant join |
| `pm25_lag_k` (k=1,2,3,6,12,24) | `groupby(station).shift(k)` | past only |
| `pm25_roll_mean_6/24` | rolling mean ending at t | includes t, not t+1 |
| weather at t + `_lag_1` | temp / RH / wind | no weather at t+1 |
| `*_missing` | 1 if weather null before impute | OK |
| Weather NaN fill | **train median only**, applied to all splits | no test median leak |

## Dropped rows

- Missing target (`pm25` at t+1 null) — no synthetic ground truth
- Missing any `pm25_lag_*` / `pm25_roll_mean_*` — need ≥24h history per station

## Out of scope (P10e optional)

Episode flags, multi-horizon, pollutant co-lags beyond weather/PM2.5 v1.
