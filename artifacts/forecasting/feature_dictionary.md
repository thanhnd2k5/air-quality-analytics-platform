# Phase 10b – Forecast feature dictionary

Target: **`y_pm25_tplus1`** = PM2.5 at station hour **t+1**, using only information available at **t**.  
Feature set: **`v1_1_episode_pollutant`**.

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
| `pm25_ug_m3` | Observed at t — also a **model feature** + persistence baseline |
| `season` | String; model uses `season_code` |

## Features (v1.1)

| Feature | Construction | Leakage note |
|---------|----------------|--------------|
| `hour` | `time_key` at t | OK |
| `month`, `day_of_week`, `season_code` | from `dim_date` at t | OK |
| `station_key`, `cluster_id` | station + Phase 9 mart | time-invariant join |
| `pm25_ug_m3` | PM2.5 at t (nowcast input) | OK at prediction time |
| `pm25_lag_k` (k=1,2,3,6,12,24) | `groupby(station).shift(k)` = t−k | past only |
| `pm25_roll_mean_6/24` | rolling mean ending at t | includes t, not t+1 |
| `pm25_delta_1` | `pm25(t) − pm25(t−1)` | past only |
| weather at t + `_lag_1` | temp / RH / wind | no weather at t+1 |
| `*_missing` (weather) | 1 if weather null before impute | OK |
| `pm10/no2/co_lag_1` (+ missing) | co-pollutant lag-1 | past only; null → train median |
| `hours_into_dirty_run` | consecutive dirty hours ending at t (PM2.5 ≥ 115; null breaks) | causal |
| `in_episode_flag` | 1 iff streak ≥ 3 at t | **no look-ahead** (hour 1–2 of a run stay 0) |
| `hours_since_last_episode` | hours since last `in_episode_flag=1` | NaN → train median |
| Weather/pollutant/episode-since fill | **train median only** | no test median leak |

## Baseline

Persistence: `y_hat(t+1) = pm25_ug_m3` at origin t (not `pm25_lag_1`).

## Dropped rows

- Missing target (`pm25` at t+1 null) — no synthetic ground truth
- Missing `pm25_ug_m3` at t — cannot form persistence / core nowcast feature
- Missing any `pm25_lag_*` / `pm25_roll_mean_*` / `pm25_delta_1` — need ≥24h history per station

## Out of scope

Multi-horizon targets; regional concurrent K-station flag; using full mart episode end times (would leak).
