# Spatial + calendar ablation — promote candidate, lock unchanged

**Decision:** `PROMOTE_CANDIDATE` for nearest-neighbor PM2.5 features. Calendar flags alone stay `KEEP_BASELINE`. The HistGB v2 lock was not modified.

**Source:** `artifacts/forecasting/spatial_calendar_ablation/ablation_report.json`  
**Row set:** all 372,499 rows of `feature_matrix_v2.parquet` (M0 retrained on this set reproduces the locked test MAE of 8.872 and the December-test MAE of 14.080). HistGB v2 hyperparameters, sample weights, and the train / val / test split are unchanged.

The promote bar is the same one used to close the PBL branch: validation and test ΔMAE ≤ −0.15 µg/m³, winter-test and high-PM test not worse by more than 0.10, and at least 7 of 12 stations improved.

## What the winter errors actually are

Signed error is prediction minus actual. On the locked model, December 2016 (the entire winter-test slice) has mean signed error **+1.01 µg/m³**. The model is not uniformly low in winter. It is late.

| Winter-test slice (Dec 2016) | n | MAE | Mean signed error | Response ratio |
|---|---:|---:|---:|---:|
| All hours | 8,478 | 14.080 | +1.01 | — |
| Episode body (level already high) | 1,969 | 11.15 | −0.04 | — |
| Rising hours inside an episode | 806 | 36.92 | −36.3 | 0.21 |
| Episode peak hour | 197 | 24.14 | −17.8 | 0.22 |
| Falling hours (drop ≥ 20) | 612 | 35.47 | +33.9 | 0.23 |

Response ratio is the mean predicted hour-ahead change divided by the mean actual change. On a fast rise the locked model moves about one fifth of the way. On a fast drop it stays high. Bins below 150 µg/m³ are biased high; bins at or above 150 are biased low, and the bias grows with the level (−1.9 at 150–250, −5.6 at 250–500, −25 at ≥500).

On those December rise hours, the three nearest stations were already at least 10 µg/m³ higher 51% of the time. Signed error was −37.1 when neighbors led and −29.1 when they did not. That is the spatial opening. It is not the whole miss: January–February 2016 (validation winter) also under-reacts to rises, and there the neighbor-lead correlation is about zero.

Chinese New Year is not in the test split. Test starts 2016-07-01, so winter-test is December only. The 2016 firework window (7–8 Feb) is in validation: locked MAE 40.2, mean signed error −20.7, and HistGB is worse than persistence there (persistence MAE 35.3).

## Ablation (model − M0, µg/m³)

| Model | Added features | Val | Test | Winter test | Heating test (15 Nov–15 Mar) | High-PM test (≥115) | Rapid-rise test | Episode-peak test | Stations improved |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| M1 | Calendar / heating | +0.006 | −0.012 | −0.019 | −0.008 | −0.024 | −0.049 | −0.128 | 7/12 |
| M2 | 3-neighbor PM2.5 | −0.378 | −0.298 | −0.400 | −0.425 | −0.545 | −1.929 | +0.065 | 11/12 |
| M3 | Calendar + spatial | −0.372 | −0.336 | −0.502 | −0.481 | −0.617 | −1.960 | +0.126 | 12/12 |

M1 does not clear the bar. Its one clear effect is the validation firework window (ΔMAE −1.91, signed error from −20.7 to −14.9). The test set has zero such hours, so that effect cannot be confirmed on the locked test split. Statutory heating and the adjusted label (2013–14 extended through 17 Mar; 2016–17 started 13 Nov) tell the same story: calendar flags barely move December.

M2 and M3 both clear the bar. M3 is the better December / high-PM / heating test model. M2 is the more stable one: validation winter improves by −0.483 with spatial alone and only −0.349 once calendar flags are added. Calendar on top of spatial is a small test gain and a validation-winter giveback.

## What did not improve

- Fast-rise response ratio on test goes from 0.20 to 0.27. The model still forecasts about a quarter of the observed jump.
- The single peak hour of each test episode is slightly worse (M2 +0.065, M3 +0.126).
- December hours with actual PM2.5 ≥ 500 (n = 77) get worse: MAE 43.4 → 50.8 (M2) / 51.2 (M3), and the low bias deepens.
- Winter-test MAE at Huairou, Gucheng, and Shunyi does not improve. Huairou’s nearest neighbor is 22 km away; core stations are 4–8 km apart, and those core stations take almost all of the December gain (Tiantan −1.03, Guanyuan −1.04, Dongsi −0.94 µg/m³ under M2).

## Leakage

Neighbor features are an inverse-distance mean of the three nearest stations at origin t (`neighbor_pm25_mean`), at t−1h, and at t−3h. `spatial_gradient` is own PM2.5(t) minus the mean at t. Neighbor PM2.5 at t+1 is not read. Calendar flags are functions of the clock only. `hours_from_cny_midnight` is signed hours from lunar-new-year midnight and is null outside ±72 hours. High-PM, rapid-rise, and episode-peak labels are applied after the forecast, from actual PM2.5.

## What to do next

Do not edit the lock in this step. Spatial features are the first add-on in this series that clears the gate PBL and EDGAR did not. A later promote choice is M2 if validation winter matters more, or M3 if the December and high-PM test slices are the target. Upwind features are the sensible follow-up for the stations whose neighbors are tens of kilometres away, and for the rise that is still mostly missed. Calendar flags are worth keeping only as a CNY-window experiment; they are not a winter-test fix on this split.
