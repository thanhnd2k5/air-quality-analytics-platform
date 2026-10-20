# Upwind POC — one round, keep M2

**Decision:** `KEEP_M2`  
**Lock:** unchanged. M2 stays `PROMOTE_CANDIDATE`. M4 is not promoted.  
**Source:** `artifacts/forecasting/upwind_poc/ablation_report.json`  
This was a single fit. The formula was fixed in `src/forecasting/upwind.py` before training. 2016-12-20 was a safety check, not a target the weights were adjusted to.

## What Gucheng on 20 Dec actually did

The three nearest stations sit northeast to east-southeast of Gucheng: Wanliu at bearing 47° (12.0 km), Guanyuan at 83° (13.3 km), Wanshouxigong at 106° (14.9 km).

From the 09:00 target hour onward, those three were far below Gucheng, and M2 followed them down. M0, which only sees the local level, did not.

| Origin t | PM2.5 t | PM2.5 t+1 | Nearest-3 minus Gucheng | Wind | M0 signed | M2 signed |
|---|---:|---:|---:|---|---:|---:|
| 08:00 | 448 | 521 | −88 | N, 0.9 m/s | −79 | −113 |
| 09:00 | 521 | 593 | −211 | ENE, 1.0 m/s | −6 | −122 |
| 12:00 | 517 | 628 | −201 | SSE, 2.6 m/s | −21 | −125 |
| 15:00 | 628 | 634 | −374 | SW, 0.1 m/s | −132 | −212 |

At 09:00, M0 is almost on the next hour (signed −6) and M2 is 122 µg/m³ low. At 15:00 Wanshouxigong reads 3 µg/m³, which pulls the nearest-3 mean to 254 against Gucheng at 628. Hourly rows: `gucheng_20161220_hourly.csv`.

Changping was as high as Gucheng at 09:00 (507 vs 521) and higher at 12:00 (557 vs 517). It lies to the north, outside the nearest three. At those hours the wind was ENE and then SSE, so Changping was not the upwind station. A wind-weighted mean was not going to copy Changping’s level without being fitted to this day.

## Formula that was trained once

Meteorological direction: 0° means the wind comes from the north. Every other station can contribute. Weight is `max(0, cos(bearing − wind_from)) / distance`. Downwind weight is 0. Features added on top of M2, using only t and t−1h:

- `upwind_pm25`, `upwind_pm25_lag1`
- `upwind_minus_local` = upwind mean minus local PM2.5
- `upwind_unavailable` when direction is missing or no station with data sits upwind
- `upwind_weak_wind` when speed is under 1 m/s; the concentration features are then null

Weak wind is 27.6% of rows. Unavailable is 9.1%. Neighbor PM2.5 at t+1 is not read.

## Ablation, one shot (µg/m³)

M0 test MAE is 8.872, the same lock reproduction as the spatial round.

| Comparison | Val | Test | Winter test | High-PM test | Rapid-rise test |
|---|---:|---:|---:|---:|---:|
| M4 − M0 | −0.478 | −0.404 | −0.540 | −0.601 | −2.447 |
| M4 − M2 | −0.100 | −0.106 | −0.140 | −0.056 | −0.518 |

M4 beats the original M0 gate (12/12 stations) and does not give back the M2 gain on those average slices. Fast-rise response ratio moves 0.205 → 0.265 → 0.286. The average problem gets a bit better. The tail does not.

Gucheng on 20 Dec, actual ≥ 500 (13 station-hours, including the short 04:00–05:00 spike): MAE 69.2 (M0), 101.3 (M2), 103.9 (M4). The pre-registered severe line was ΔMAE vs M0 above +10. M4 is +34.7, slightly worse than M2’s +32.1. The long afternoon run 12:00–20:00 is MAE 47.4 / 83.3 / 82.5. Upwind does not undo the nearest-neighbor pull-down, because those M2 features stay in the model.

Across 24 test episodes at ≥500, M4 beats M2 on 13 and M0 on 10. The pooled ≥500 test MAE is 43.4 / 50.8 / 50.9. Validation’s 73 hours at ≥500 go the other way (M2 and M4 both about −33 vs M0), so the test tail is not “spatial always fails above 500”. It is still too small a set of independent episodes to call the failure general, and this one afternoon is large enough to miss the safety bar.

Suburban winter ΔMAE of M4 vs M0: Shunyi −0.23, Gucheng +0.27, Huairou +0.38. Upwind helps Shunyi’s winter and does not repair Gucheng or Huairou.

## Status

| Branch | Decision |
|---|---|
| PBL | `CLOSE_BRANCH` |
| EDGAR | `EDA_ONLY` |
| Calendar | `EDA_ONLY` |
| Spatial M2 | `PROMOTE_CANDIDATE` |
| M3 | backup candidate |
| Upwind M4 | `KEEP_M2` — POC finished, one round |
| HistGB v2 | lock unchanged |

M4 shows that a wind-weighted neighbor mean can still lower average and fast-rise error. It does not fix a local extreme that the nearest stations do not share, and it was not refit to make 20 Dec look better. That is a complete result for this branch. Further upwind tuning on that date would no longer be a fair test.
