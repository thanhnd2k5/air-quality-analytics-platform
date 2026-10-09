# Phase 8e – Candidate ML features (for Phase 10)

Target (locked in `PROJECT_CONTEXT.md`): forecast **PM2.5(t+1 hour)** using only information available at time **t**.  
Do **not** use same-hour weather/pollutant at t+1, or any future labels.

Source tables: `dwh.fact_air_quality_hourly`, dims, `mart.mart_pm25_episodes` (flags derived offline then joined carefully without leakage).

## A. Calendar / time (high priority)

| Feature | Rationale from P8b |
|---------|-------------------|
| `hour` / `time_key` | Diurnal peak ~22:00, trough ~07:00 |
| `month`, `season` | Winter ≫ summer (mean 95.5 vs 64.7) |
| `day_of_week`, `is_weekend` | Standard temporal control |
| `year` / trend proxy | Year means differ; 2017 partial — treat carefully in split |

## B. PM2.5 history (core)

| Feature | Notes |
|---------|--------|
| `pm25_lag_1` … `pm25_lag_24` (and maybe 48) | Persistence is strong for hourly AQ |
| Rolling mean/std over 3h, 6h, 12h, 24h **ending at t** | Captures build-up into episodes |
| Delta: `pm25_t - pm25_t-1` | Short-term change |

## C. Other pollutants (supporting, lagged only)

From P8b correlations with PM2.5 (sample): PM10 0.89, CO 0.80, NO2 0.67, SO2 0.48, O3 −0.15.

| Feature | Notes |
|---------|--------|
| Lags of PM10, NO2, CO (1–24h) | Strong co-movement; keep leakage-safe |
| O3 lag | Weaker / inverse — optional, low priority |
| Same-hour pollutant at t | Allowed for *nowcast* style inputs at prediction time; still **not** t+1 |

## D. Weather (resolved fact; prefer lags)

P8b: RH +0.38, wind −0.27, temp −0.13 with PM2.5 (pattern only).  
P8c episodes: colder, higher RH, weaker wind inside episodes vs baseline.

| Feature | Notes |
|---------|--------|
| `temperature_c`, `relative_humidity_pct`, `wind_speed_m_s` at **t** and lags 1–6 | Strongest weather signals |
| `rain_mm`, `cloud_cover_pct`, `pressure_hpa`, `dew_point_c` | Weaker; keep if cheap |
| `wind_direction` (categorical / sin-cos) | Optional |
| `*_source` flags | Quality / fill awareness (UCI vs Open-Meteo) |

**Avoid:** using weather at t+1; claiming causal effect in reports.

## E. Station identity

| Feature | Notes |
|---------|--------|
| `station_key` / station embedding / one-hot | Dongsi high vs Dingling low — station effect is real |
| District | Optional; overlaps but does not replace cluster (e.g. Shunyi → elevated_core) |
| `cluster_id` / `cluster_label` | **Phase 9 locked** — join `mart.mart_station_cluster` (KMeans K=2: `elevated_core` vs `cleaner_outskirts`). Station-level, time-invariant → no temporal leakage |

## F. Episode-derived (use with care)

Locked rule: PM2.5 ≥ 115 for ≥ 3h; multi-station K=6 (`episode_definition.md`).

| Feature at time t | Safe construction |
|-------------------|-------------------|
| `in_episode_flag` | 1 if hour t is inside a station episode computed from history **≤ t** only (or precomputed offline with causal mask) |
| `hours_into_episode` | Count of consecutive dirty hours ending at t (if ≥1) |
| `hours_since_last_episode` | Gap since previous episode end ≤ t |
| `regional_active_flag` | 1 if ≥ K stations in episode at t (from concurrent count ≤ t) |

Do **not** attach future episode end time or full-episode mean to row t during training without a causal cutoff.

## G. Explicitly out of scope / deferred

- Imputed PM2.5 as if observed (keep missingness flags instead)
- Raw CSV features that bypass DWH
- Multi-horizon targets beyond t+1 until Phase 10 scope expands

## Suggested Phase 10 starter set

1. Calendar: hour, month/season  
2. PM2.5 lags 1, 2, 3, 6, 12, 24 + rolling 6h/24h mean  
3. Weather at t: temp, RH, wind (+ lag 1)  
4. Station id  
5. Optional: `cluster_id` from `mart.mart_station_cluster`; PM10/NO2 lag 1; `in_episode_flag` / `hours_into_episode`

Evaluate with time-based split (e.g. last months / last year held out), not random rows.

## Phase 10 lock (2026-10-10, v1.1)

- Feature set **`v1_1_episode_pollutant`**: starter + `pm25_ug_m3` + `cluster_id` + `pm25_delta_1` + causal episode flags + PM10/NO2/CO lag-1
- Persistence baseline = PM2.5(t), not lag_1
- Episode features are **causal** (no look-ahead to future dirty hours); see `artifacts/forecasting/feature_dictionary.md`
- Metrics: `artifacts/forecasting/model_lock.json` / `error_analysis.md`
