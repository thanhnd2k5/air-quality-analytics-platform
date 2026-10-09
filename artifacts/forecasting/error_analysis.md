# Phase 10e – Forecast error analysis

**Locked model:** HistGradientBoosting (global, PM2.5 t+1h)  
**Primary test:** 2016-07-01 → 2016-12-31  
**Test n:** 48,781

## Overall (test)

| Model | MAE | RMSE | R² |
|-------|-----|------|----|
| Persistence | 9.783 | 18.012 | 0.9498 |
| **HistGB (locked)** | **9.006** | **16.247** | **0.9592** |

MAE lift vs persistence: **0.777** µg/m³ (7.9% relative).

## By station (test)

- Best MAE: **Huairou** (7.30) — cluster `cleaner_outskirts`
- Worst MAE: **Dongsi** (10.04) — cluster `elevated_core`

Full table: `error_by_station_test.csv`.

![MAE by station](figures/error_mae_by_station.png)

## By cluster (test)

| cluster | label | n | MAE | Persistence MAE | Lift |
|---------|-------|---|-----|-----------------|------|
| 0 | `elevated_core` | 36653 | 9.36 | 10.23 | 0.87 |
| 1 | `cleaner_outskirts` | 12128 | 7.94 | 8.42 | 0.48 |

## By season (test)

| season | n | MAE | Persistence MAE |
|--------|---|-----|-----------------|
| summer | 16411 | 6.90 | 7.42 |
| autumn | 23892 | 8.45 | 9.33 |
| winter | 8478 | 14.64 | 15.61 |

![MAE by hour](figures/error_mae_by_hour.png)

![Actual vs pred](figures/error_actual_vs_pred.png)

![MAE by actual bin](figures/error_mae_by_actual_bin.png)

## Where errors hurt most

- Absolute error grows with **high actual PM2.5** (episode / pollution peaks) — see `error_residual_by_actual_bin_test.csv`.
- Persistence remains strong hour-to-hour; HistGB gain is largest where weather / lags / station structure add signal beyond lag-1.

### Worst station-days (test, by mean abs error)

| day | station | MAE | max\|err\| | mean actual |
|-----|---------|-----|-----------|-------------|
| 2016-12-20 | Wanliu | 68.5 | 257.3 | 355.6 |
| 2016-12-20 | Wanshouxigong | 61.7 | 538.8 | 409.0 |
| 2016-12-20 | Gucheng | 58.2 | 359.6 | 476.3 |
| 2016-07-26 | Wanshouxigong | 55.5 | 235.2 | 53.6 |
| 2016-12-20 | Guanyuan | 48.9 | 186.4 | 408.2 |
| 2016-12-16 | Dongsi | 46.2 | 169.2 | 139.8 |
| 2016-12-20 | Dongsi | 44.8 | 190.7 | 405.1 |
| 2016-12-30 | Dongsi | 43.9 | 147.9 | 282.9 |

## 2017 sensitivity (optional, not DoD)

2017 Jan–Feb only (winter-biased); not primary DoD

- n = 15,813
- HistGB MAE = **12.552**
- Persistence MAE = **12.609**
- Beats persistence: **True**

Interpret cautiously: Jan–Feb 2017 is winter-only and short.

## Artifacts

- `error_by_*.csv`, `error_worst_days_test.csv`
- `error_analysis.md` (this file)
- figures under `artifacts/forecasting/figures/`
- mart: `mart.mart_pm25_predictions`

