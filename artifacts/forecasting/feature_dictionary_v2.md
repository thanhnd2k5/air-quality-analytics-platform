# Forecast feature dictionary v2 (Vòng A)

Target: **`y_pm25_tplus1`** = PM2.5 at station hour **t+1**, using only information available at **t**.

Same split / window as Phase 10 lock. This matrix is **experimental** — does not replace v1 production lock.

## Features (v2 = v1 +)

| Feature | Construction | Leakage note |
|---------|----------------|--------------|
| (all v1 features) | see `feature_dictionary.md` | unchanged |
| `pm25_delta_1` | PM2.5(t) − PM2.5(t−1) | past + t only |
| `pm10_ug_m3`, `co_ug_m3`, `no2_ug_m3` | co-pollutant at t | OK at prediction time |
| `*_lag_{1,2,3,6}` | groupby(station).shift(k) | past only |
| `*_missing` | 1 if pollutant null before impute | OK |
| Pollutant NaN fill | **train median only** | no test median leak |
| `hours_into_episode` | consecutive PM2.5≥115 hours ending at t | causal streak |
| `in_episode_flag` | 1 if streak ≥ 3 | no future island length |

## Explicitly not in v2

O3/SO2, cloud_cover, `hours_since_last_episode`, regional K=6, LSTM.

## Baseline

Persistence: `y_hat(t+1) = pm25_ug_m3` at origin t.
