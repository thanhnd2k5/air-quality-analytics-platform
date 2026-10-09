# Reusable forecasting SQL (Phase 10)

Read-only against `dwh` / `mart` for extract and smoke. Target: **PM2.5(t+1h)**.

## ML window (primary)

- `2013-03-01 00:00:00` → `2016-12-31 23:00:00`
- Split: Train → 2015-12 | Val 2016 H1 | Test 2016 H2
- 2017 excluded from primary eval (partial year / winter-biased); optional sensitivity later

## Starter files

- `smoke_forecasting_prereqs.sql` — P10a gate (fact span + cluster join)
- `extract_forecast_base.sql` — P10b base extract (fact + dim_date + cluster)

## Python

- `scripts/smoke_forecasting_phase10.py` → `artifacts/forecasting/kickoff_smoke.json`
- `scripts/run_forecasting_phase10b.py` → `feature_matrix.parquet` + `feature_qc.json` + `feature_dictionary.md`
- `scripts/run_forecasting_phase10c.py` → `model_lock.json` + metrics + `models/pm25_forecast/`
- `scripts/run_forecasting_phase10d.py` → staging COPY + `mart.mart_pm25_predictions` + `mart_prediction_checks.json`
