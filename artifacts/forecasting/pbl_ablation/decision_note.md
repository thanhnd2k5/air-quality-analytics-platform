# PBL branch — closed

**Decision:** `CLOSE_BRANCH`  
**Source:** `artifacts/forecasting/pbl_ablation/ablation_report.json` (finished 2026-10-19)  
**Feature tested:** `pbl_lag_1` = Open-Meteo `boundary_layer_height` at t−1, within station. Same rows for M0 and M1 (12 rows dropped for a null lag). HistGB v2 hyperparameters and sample weights unchanged. The model lock was not modified.

## Ablation (M1 − M0, µg/m³)

Promote required val and test ΔMAE ≤ −0.15, winter-test and high-PM test not worse by more than 0.10, and at least 7 of 12 stations improved.

| Slice | ΔMAE |
|---|---:|
| Validation (2016 H1) | −0.005 |
| Test (2016 H2) | −0.017 |
| Winter test | −0.010 |
| Test hours with PM2.5 ≥ 115 | −0.036 |

Ten of twelve stations improved on test. Guanyuan (+0.011) and Wanliu (+0.048) did not (`delta_mae_by_station_test.csv`). The gains are below the promote threshold.

## What the association still shows

On Wanshouxigong in 2015 (`artifacts/openmeteo/poc_pbl/wanshouxigong_2015-01-01_2015-12-31_pbl_report.json`):

- Hourly Pearson of PBL height vs PM2.5 is −0.23 (Spearman −0.31).
- Hours with PM2.5 ≥ 115 have mean PBL 289 m. Other hours have mean PBL 609 m.
- After hour, temperature, and wind speed, partial Pearson of `pbl_lag_1` vs PM2.5 is −0.05.

Wind and temperature already in HistGB v2 account for almost all of the PBL association. Do not ingest PBL and do not rerun this ablation unless the promote threshold or the feature definition changes.
