# Spatial data quality — review flag frozen, values unchanged

**Decision:** diagnostic only. The original PM2.5 series stays as published. A separate `suspect_spatiotemporal` flag marks isolated collapses for review. No aggregator is promoted, and the HistGB v2 lock is unchanged. M2 remains `PROMOTE_CANDIDATE`.

**Source:** `artifacts/forecasting/spatial_quality/quality_report.json`  
**Rule:** `src/forecasting/spatial_quality.py`  
The cuts were frozen from the train split before validation or test counts were used. 2016-12-20 is a reconciliation case in the report script. It is not an argument of the scorer.

## The value 3 is in the UCI file

Wanshouxigong, 2016-12-20 15:00, source row 33376 of `PRSA_Data_Wanshouxigong_20130301-20170228.csv`:

| Field | UCI | Locked feature matrix |
|---|---:|---:|
| PM2.5 | 3 | 3 |
| PM10 | 89 | 89 |
| CO | 8800 | 8800 |
| NO2 | 197 | 197 |

The file is 2,871,076 bytes, the inventory size. The matrix stores the same hour with pollutant-missing flags at 0, on the test split. Across all 372,499 overlapping matrix rows, UCI PM2.5 and matrix PM2.5 differ in 0 rows. The 3 was not created by ingestion, and it was not filled in later.

SO2 at that hour is 5. The next hour at the same station is 170 and the hour after that is 398. Those later hours stay in their own rows. This diagnostic does not copy either of them onto 15:00.

## What the flag is

A station-hour is `suspect_spatiotemporal` when both adjacent hours and at least two of the three nearest stations are present, and the reading is at most half of the lower of those two contexts:

- temporal floor = min(PM2.5 at t−1h, PM2.5 at t+1h)
- spatial median = median of the three nearest stations at t
- context = min(temporal floor, spatial median)
- isolation = min(1 − PM2.5 / temporal floor, 1 − PM2.5 / spatial median)
- flag when context ≥ 50 µg/m³ and isolation ≥ 0.5

The original PM2.5 is copied through. PM10 and CO are context columns (`pm10_context`, `co_elevated`), not a second gate. A flagged hour still has to be read in context: some have PM10 in the hundreds, some have PM10 on the same floor as PM2.5, and some sit just above the cut.

On train, with context ≥ 50, the 99.9th percentile of isolation is 0.333. That quantile still describes ordinary gradients (train median PM2.5 in the 0.4 cut is 27). Isolation 0.5 is the round cut above it where the train flagged set’s median PM2.5 is 3 and the median gap is 67 µg/m³ (55 hours). Validation was not used to move either number.

| Cut (context, isolation) | Train | Val | Test | Train median PM2.5 | Train median gap |
|---|---:|---:|---:|---:|---:|
| 50, 0.4 | 85 | 11 | 11 | 27 | 56 |
| **50, 0.5 (frozen)** | **55** | **4** | **7** | **3** | **67** |
| 50, 0.6 | 45 | 2 | 4 | 3 | 73 |
| 75, 0.5 | 31 | 1 | 5 | 3 | 94 |

Scored hours: train 298,368, validation 52,416, test 52,992. The frozen flag is 55 / 4 / 7 of those. 2013 holds 25 of the 55 train flags; 2014 and 2015 hold 15 each. The same shape already exists on train, for example Gucheng 2014-02-25 23:00 (PM2.5 3, PM10 469, CO 7000, isolation 0.991).

PM2.5 equal to 3 is common and usually consistent with the neighborhood: train 6,505 such hours, of which 28 are flagged; validation 916, of which 0 are flagged; test 933, of which 4 are flagged.

The flag uses t+1, so it is an offline review mark. The same cuts with only t−1 (`suspect_spatiotemporal_causal`) mark 643 / 73 / 98 hours. A real drop that stays down is included there. That wider mark is the wrong tool for an automatic exclusion.

## Mean, median, trimmed mean

Neighbors are the same three stations M2 uses, with the same inverse-distance weights. With three finite values, trimming both the lowest and the highest leaves the middle value, which is the median. The trimmed mean here drops only the neighbor farthest from the median and averages the other two. Nothing is written back into PM2.5.

On ordinary hours the three aggregates agree at the center. Test, 52,629 hours with at least two finite neighbors: the median of (IDW − median) is +0.01 µg/m³. |IDW − median| exceeds 20 on 4.6% of hours and 50 on 0.8%. Leaving a suspect neighbor out of the IDW changes the bulk by nothing at the 99th percentile (0.038% of test hours move by more than 10).

The sensitivity shows up on the hours that actually have a suspect neighbor. Test has 22 such origin hours. There the median IDW sits 26 µg/m³ below the three-neighbor median, and 39 µg/m³ below the IDW that treats the suspect neighbor as unavailable. 20 of those 22 hours move by more than 10 µg/m³. Train shows the same direction on 149 hours (median pull −27 µg/m³). Inverse-distance weighting gives the nearest station the largest weight, so a suspect nearest neighbor moves the IDW more than an unweighted mean.

## Reconciliation hour, after the rule was frozen

Wanshouxigong 15:00 has isolation 0.982 and context 170 (temporal floor 170, spatial median of its neighbors 420). PM10 89 against PM2.5 3, CO 8800. The frozen rule flags it. The hour was not used to choose the cut.

Stations that take Wanshouxigong as one of three neighbors at that hour:

| Origin | Own PM2.5 | Neighbor values | IDW | Mean | Median | Trimmed | IDW with the suspect hour left out |
|---|---:|---|---:|---:|---:|---:|---:|
| Gucheng | 628 | Wanliu 338, Guanyuan 420, Wanshouxigong 3 | 266 | 254 | 338 | 379 | 377 |
| Guanyuan | 420 | Wanshouxigong 3, Dongsi 449, Tiantan 403 | 266 | 285 | 403 | 426 | 427 |
| Tiantan | 403 | Wanshouxigong 3, Dongsi 449, Nongzhanguan 391 | 266 | 281 | 391 | 420 | 426 |

At Gucheng the 3 pulls the IDW from 377 down to 266. The median (338) and the trimmed mean (379) move less. After that pull is removed, the robust aggregate is still about 250 µg/m³ below Gucheng, because Wanliu at 338 and Guanyuan at 420 are the recorded neighbor levels. A robust aggregate absorbs one inconsistent neighbor. It does not create agreement with a station the other neighbors do not match.

The other six test flags are in `suspect_rows.csv`. Three of them sit on the cut (isolation about 0.52; PM2.5 28, 75 and 52) with PM10 in line with PM2.5. Four, including this hour, have isolation above 0.94. They are not one class. The cut stays where train put it; moving it after reading the test list would spend the confirmation set.

## What was left open, and what closed it

The median comparison was run once as Robust Spatial M5 and closed `KEEP_M2`. See `artifacts/forecasting/robust_spatial_poc/decision_note.md`. Trimmed mean, winsorized mean, and blends with IDW are not to be fit on this test set. The offline flag uses t+1, so it stays a review column. It is not evidence enough for automatic exclusion in serving, and it does not change stored PM2.5. 2016-12-20 stays a case study, not a tuning target.

| Branch | Status |
|---|---|
| Spatial M2 | `PROMOTE_CANDIDATE` — unchanged by this diagnostic |
| Upwind M4 | `KEEP_M2` |
| Robust spatial M5 | `KEEP_M2` — closed after this diagnostic; see robust_spatial_poc |
| Spatial data quality | diagnostic — flag frozen, PM2.5 unchanged, lock unchanged |
