# Phase 8c – PM2.5 episode definition (LOCKED)

## Locked rule (use in dbt marts / P8d)

| Parameter | Value | Why |
|-----------|-------|-----|
| `threshold_ug_m3` | **115** | Near global P75≈111; marks *elevated* hours, not the long-run mean (~80). More selective than 75; less extreme-only than P90≈185. |
| `min_hours` | **3** | Drops one-hour spikes; sensitivity shows 1h inflates counts heavily vs 3h. |
| `multi_station_k` | **6** | Network is highly coherent (n≥3 already ~28.18% of hours; n=12 alone common). **K=6** = half of 12 stations marks *regional* events without requiring near city-wide. |
| Null handling | **cut** | Null PM2.5 is not dirty and breaks a run (no bridging). |

Global reference percentiles (hourly non-null PM2.5): P90=185.0, P95=242.0.

### Concurrent rarity under locked 115 / 3h

- Hours with n≥3: **28.18%**
- Hours with n≥6: **23.22%**
- Hours with n≥9: **18.23%**

## Formal definition

1. A station-hour is **dirty** iff `pm25_ug_m3 >= 115` (null ⇒ not dirty).
2. A **station episode** is a maximal run of consecutive dirty hours at one station with length `>= 3`.
3. For each timestamp, `n_stations_in_episode` = count of stations whose hour belongs to a station episode.
4. A **multi-station event** is a maximal run of hours with `n_stations_in_episode >= 6`.

Not a realtime detector — historical analytics only.

## Sensitivity grid (summary)

| threshold | min_h | episodes | dur_median | dur_p90 | multi events K=3/6/9 |
|-----------|------:|---------:|-----------:|--------:|----------------------|
| 75 | 1 | 12573 | 6.0 | 35.0 | 838 / 823 / 798 |
| 75 | 3 | 8582 | 11.0 | 44.0 | 652 / 658 / 646 |
| 75 | 6 | 6362 | 16.0 | 51.0 | 517 / 504 / 499 |
| 115 | 1 | 9478 | 5.0 | 26.0 | 708 / 636 / 530 |
| 115 | 3 | 6318 | 9.0 | 36.0 | 523 / 487 / 427 |
| 115 | 6 | 4353 | 13.0 | 43.0 | 388 / 348 / 313 |
| P90_185 | 1 | 4735 | 4.0 | 23.0 | 363 / 305 / 244 |
| P90_185 | 3 | 2985 | 8.0 | 30.0 | 266 / 231 / 186 |
| P90_185 | 6 | 1889 | 14.0 | 39.0 | 165 / 157 / 129 |
| P95_242 | 1 | 2776 | 4.0 | 19.0 | 218 / 161 / 152 |
| P95_242 | 3 | 1730 | 8.0 | 24.0 | 160 / 130 / 115 |
| P95_242 | 6 | 1113 | 11.0 | 30.0 | 105 / 93 / 76 |

Full CSV: `artifacts/eda/episode_sensitivity_grid.csv`.

## Locked results (quick)

- Station episodes: **6318** across **12** stations
- Duration hours: median **9.0**, P90 **36.0**, mean **14.89**
- By season: `{'autumn': 1423, 'spring': 1594, 'summer': 1476, 'winter': 1825}`
- By year: `{2013: 1423, 2014: 1745, 2015: 1510, 2016: 1421, 2017: 219}`
- Multi-station events (K=6): **487** (median duration 10.0 h)

### Top stations by episode count
- Dongsi: 596 episodes, median duration 9.0h
- Nongzhanguan: 580 episodes, median duration 9.0h
- Gucheng: 568 episodes, median duration 8.0h
- Wanshouxigong: 567 episodes, median duration 9.0h
- Shunyi: 560 episodes, median duration 9.0h

## Weather inside episodes vs baseline (pattern only)

Episode hours: 94105; baseline hours: 326663.

| Metric | Inside episode | Baseline |
|--------|----------------|----------|
| PM2.5 avg | 198.32 | 44.71 |
| Temp °C | 10.77 | 14.33 |
| RH % | 67.12 | 49.26 |
| Wind m/s | 1.25 | 1.87 |
| Rain mm (mean hour) | 0.036 | 0.073 |
| Cloud % | 46.98 | 39.13 |

Interpretation: descriptive co-occurrence only — do **not** claim causality.

## Artifacts for P8d

- `episodes_station_locked.csv` — grain preview for `mart_pm25_episodes`
- `episodes_multi_station_locked.csv` — grain preview for `mart_pm25_multi_station_events`
- `episode_lock_summary.json` — machine-readable lock + summaries
- dbt vars to set: `pm25_episode_threshold=115`, `pm25_episode_min_hours=3`, `pm25_multi_station_k=6`
