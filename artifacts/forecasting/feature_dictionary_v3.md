# Forecast feature dictionary v3 (O3/SO2 + cloud_cover)

Target: **`y_pm25_tplus1`** = PM2.5 at station hour **t+1**, using only information available at **t**.

Same split / window as production lock. This matrix is **experimental** — does not replace v2 production lock.

## Features (v3 = v2 +)

| Feature | Construction | Leakage note |
|---------|----------------|--------------|
| (all v2 features) | see `feature_dictionary_v2.md` | unchanged |
| `o3_ug_m3`, `so2_ug_m3` | co-pollutant at t | OK at prediction time |
| `o3_*` / `so2_*` lags 1,2,3,6 | groupby(station).shift(k) | past only |
| `o3_ug_m3_missing`, `so2_ug_m3_missing` | 1 if null before impute | OK |
| `cloud_cover_pct` | Open-Meteo at t | OK |
| `cloud_cover_pct_lag_1` | station shift 1 | past only |
| `cloud_cover_pct_missing` | 1 if null before impute | OK |
| NaN fill | **train median only** | no test median leak |

## Explicitly not in v3

LSTM, `hours_since_last_episode`, regional K=6, HistGB retune.

## Baseline

Persistence: `y_hat(t+1) = pm25_ug_m3` at origin t. Compare to HistGB v2 production lock.
