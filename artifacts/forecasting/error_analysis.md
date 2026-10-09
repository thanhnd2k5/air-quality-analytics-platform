# Phase 10e – Forecast error analysis

**Locked model:** HistGradientBoosting (global, PM2.5 t+1h)  
**Primary test:** 2016-07-01 → 2016-12-31  
**Test n:** 48,781

## Overall (test)

| Model | MAE | RMSE | R² |
|-------|-----|------|----|
| Persistence | 9.783 | 18.012 | 0.9498 |
| **HistGB (locked)** | **9.144** | **16.503** | **0.9579** |

MAE lift vs persistence: **0.639** µg/m³ (6.5% relative).

## By station (test)

- Best MAE: **Huairou** (7.34) — cluster `cleaner_outskirts`
- Worst MAE: **Dongsi** (10.16) — cluster `elevated_core`

Full table: `error_by_station_test.csv`.

![MAE by station](figures/error_mae_by_station.png)

## By cluster (test)

| cluster | label | n | MAE | Persistence MAE | Lift |
|---------|-------|---|-----|-----------------|------|
| 0 | `elevated_core` | 36653 | 9.53 | 10.23 | 0.70 |
| 1 | `cleaner_outskirts` | 12128 | 7.97 | 8.42 | 0.45 |

## By season (test)

| season | n | MAE | Persistence MAE |
|--------|---|-----|-----------------|
| summer | 16411 | 6.97 | 7.42 |
| autumn | 23892 | 8.55 | 9.33 |
| winter | 8478 | 15.02 | 15.61 |

![MAE by hour](figures/error_mae_by_hour.png)

![Actual vs pred](figures/error_actual_vs_pred.png)

![MAE by actual bin](figures/error_mae_by_actual_bin.png)

## Where errors hurt most

- Absolute error grows with **high actual PM2.5** (episode / pollution peaks) — see `error_residual_by_actual_bin_test.csv`.
- Persistence remains strong hour-to-hour; HistGB gain is largest where weather / lags / station structure add signal beyond lag-1.

### Worst station-days (test, by mean abs error)

| day | station | MAE | max\|err\| | mean actual |
|-----|---------|-----|-----------|-------------|
| 2016-12-20 | Wanshouxigong | 78.1 | 562.5 | 409.0 |
| 2016-12-20 | Gucheng | 68.1 | 361.4 | 476.3 |
| 2016-12-20 | Wanliu | 66.1 | 247.4 | 355.6 |
| 2016-12-20 | Guanyuan | 55.5 | 183.7 | 408.2 |
| 2016-07-26 | Wanshouxigong | 54.1 | 233.9 | 53.6 |
| 2016-12-16 | Dongsi | 46.3 | 169.6 | 139.8 |
| 2016-12-20 | Dongsi | 46.0 | 182.9 | 405.1 |
| 2016-12-30 | Dongsi | 44.8 | 174.0 | 282.9 |

## 2017 sensitivity (optional, not DoD)

2017 Jan–Feb only (winter-biased); not primary DoD

- n = 15,813
- HistGB MAE = **12.960**
- Persistence MAE = **12.609**
- Beats persistence: **False**

Interpret cautiously: Jan–Feb 2017 is winter-only and short.

## Artifacts

- `error_by_*.csv`, `error_worst_days_test.csv`
- `error_analysis.md` (this file)
- figures under `artifacts/forecasting/figures/`
- mart: `mart.mart_pm25_predictions`

