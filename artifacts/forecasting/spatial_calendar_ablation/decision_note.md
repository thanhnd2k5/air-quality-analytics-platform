# Spatial + calendar ablation — promote candidate, lock unchanged

**Decision:** `PROMOTE_CANDIDATE` for M2 (three nearest neighbors). M3 stays a candidate and is not the one to take forward. Calendar alone is `EDA_ONLY`. The HistGB v2 lock was not modified, and neither candidate is promoted: the ≥500 tail gets worse under both.

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

M2 and M3 both clear the pre-registered bar. M2 is the preferred candidate. It is the more stable of the two winters: validation winter improves by −0.483 with spatial alone and only −0.349 once calendar flags are added. M3’s extra December gain is about −0.10 and does not repeat on the other winter. Calendar alone misses the promote gate (test ΔMAE −0.012). The 2016 firework window, where calendar does move error, sits entirely in validation.

## December hours at or above 500

M2 does make this tail worse. On the 77 December-2016 test hours with actual PM2.5 ≥ 500, MAE goes from 43.44 (M0) to 50.81 (M2, Δ +7.37) and 51.23 (M3, Δ +7.79). Mean signed error goes from −25.2 to −31.4 under M2. Choosing M2 instead of M3 does not avoid the tail. Both spatial models deepen the low bias there.

These 77 rows are not 77 independent observations. They are 24 station-episodes, 9 city events, and 39 distinct clock hours. Giving each clock hour one vote still leaves M2 worse (hour-mean MAE 46.8 → 57.7).

The net harm is one afternoon. Detail: `extreme_ge500_by_city_event.csv`.

| City event | Station-hours | M0 MAE | M2 MAE | ΔMAE |
|---|---:|---:|---:|---:|
| 3–4 Dec, 21:00–05:00, 6 stations | 35 | 29.83 | 29.38 | −0.45 |
| 20 Dec, 09:00–20:00, Changping / Guanyuan / Gucheng / Wanliu | 16 | 52.65 | 90.15 | +37.50 |
| The other seven events | 26 | 56.09 | 55.45 | −0.64 |

Gucheng alone accounts for 11 of those 16 hours (09:00–20:00, mean actual 580, max 646): MAE 46.5 → 89.6. The long 3–4 Dec episode, which is the largest block, is slightly better under M2. Neighbor PM2.5 at t and at t−1h is present on all 77 hours, so the miss is not a missing spatial input.

## Are neighbor readings available at forecast time?

Yes, in this pipeline, at the same vintage the lock already uses for the station’s own PM2.5(t).

`fetch_delta` orders by `event_time_local`, then completes the trailing hour: every station row at `watermark_end` is attached before the watermark may advance (`src/ingestion/db_client.py`). Serving predicts t+1 only from staging through that watermark (`docs/OPERATIONAL_DB_INGESTION_DESIGN.md` §5). Neighbor PM2.5(t) therefore arrives in the same closed hourly batch as own PM2.5(t). The ablation does not read neighbor PM2.5 at t+1.

There is no sub-hour, station-by-station arrival lag in this replay. A live feed that published stations minutes apart is not what the operational DB simulates. Across the feature matrix, `neighbor_pm25_mean` is null on 553 of 372,499 rows; HistGB already treats those as missing. On the extreme tail the feature is complete.

Wind direction is already in staging (`wind_direction` from UCI `wd`, plus Open-Meteo degrees). It is not in the locked feature set. An upwind feature can be built from columns the repository already has.

## What did not improve

- Fast-rise response ratio on test goes from 0.20 to 0.27. The model still forecasts about a quarter of the observed jump.
- The single peak hour of each test episode is slightly worse (M2 +0.065, M3 +0.126).
- The ≥500 tail above, concentrated on the afternoon of 20 Dec 2016.
- Winter-test MAE at Huairou, Gucheng, and Shunyi does not improve. Huairou’s nearest neighbor is 22 km away; core stations are 4–8 km apart, and those core stations take almost all of the December gain (Tiantan −1.03, Guanyuan −1.04, Dongsi −0.94 µg/m³ under M2).

## Leakage

Neighbor features are an inverse-distance mean of the three nearest stations at origin t (`neighbor_pm25_mean`), at t−1h, and at t−3h. `spatial_gradient` is own PM2.5(t) minus the mean at t. Neighbor PM2.5 at t+1 is not read. Calendar flags are functions of the clock only. `hours_from_cny_midnight` is signed hours from lunar-new-year midnight and is null outside ±72 hours. High-PM, rapid-rise, and episode-peak labels are applied after the forecast, from actual PM2.5.

## Research status

| Branch | Status |
|---|---|
| PBL | `CLOSE_BRANCH` |
| EDGAR | `EDA_ONLY` |
| Calendar (M1) | `EDA_ONLY` — event analysis only |
| Spatial M2 | `PROMOTE_CANDIDATE` — preferred; lock not updated |
| Spatial + calendar M3 | `PROMOTE_CANDIDATE` — not preferred |
| Upwind M4 | `KEEP_M2` — one POC round; does not replace M2 |
| HistGB v2 lock | unchanged |

The sequence is the feature-selection record: PBL had a physical association and failed the promote gate (test ΔMAE −0.017). EDGAR carries an emission contrast and has no hourly forecast ablation that beats the lock. Calendar moves the validation firework window and does not move the test set. Nearest-neighbor PM2.5 is the first add-on that clears the gate fixed before training.

## What to do next

The one upwind round is recorded in `artifacts/forecasting/upwind_poc/decision_note.md`. M4 lowers average error further and still fails the Gucheng tail, so M2 stays the candidate and the lock stays unchanged. No second upwind round.
