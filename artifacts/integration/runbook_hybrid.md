# Phase 12 – Hybrid E2E Runbook

Scope locked: **giữ volume** (không `docker compose down -v`), idempotent full chain, **1 slice fresh** (Wanshouxigong), mining **verify only** (không retrain).

## 0) Preconditions

```powershell
# Repo root; .env đã có (từ .env.example)
docker compose ps
```

**MinIO host CLI:** `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` phải khớp `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD`. Nếu `SignatureDoesNotMatch`, align trong `.env` (local only) hoặc tạm export từ container ROOT trước khi chạy script.

## 1) Infra smoke (P12b)

```powershell
docker compose up -d
docker compose ps
# Expect healthy: postgres, minio, airflow-webserver, airflow-scheduler, dashboard-api

# Airflow health (host)
Invoke-RestMethod http://127.0.0.1:8080/health
```

Evidence targets: `compose_ps.txt`, `airflow_health.json` (cùng thư mục này).

## 2) Idempotent pipeline (P12c) — expect skip

```powershell
# UCI raw → processed (12 stations)
py scripts/ingest_uci_station.py --all
py scripts/process_uci_station.py --all --process-date 2026-10-07

# Open-Meteo — skip OK nếu object đã có; không bắt buộc re-fetch full 12
py -3 scripts/ingest_openmeteo_station.py --all --ingestion-date 2026-10-07
py -3 scripts/process_openmeteo_station.py --all --process-date 2026-10-07

# Staging
py scripts/load_staging.py --all
py scripts/verify_staging_load.py --all

# dbt (image 1.9; host Postgres = postgres:5432 trong network)
docker run --rm --network air-quality-network --env-file .env `
  -e POSTGRES_HOST=postgres -e POSTGRES_PORT=5432 `
  -e DBT_SEND_ANONYMOUS_USAGE_STATS=false -e DO_NOT_TRACK=1 `
  -v "${PWD}/dbt:/dbt" ghcr.io/dbt-labs/dbt-postgres:1.9.0 `
  run --project-dir /dbt/air_quality_dbt --profiles-dir /dbt

docker run --rm --network air-quality-network --env-file .env `
  -e POSTGRES_HOST=postgres -e POSTGRES_PORT=5432 `
  -e DBT_SEND_ANONYMOUS_USAGE_STATS=false -e DO_NOT_TRACK=1 `
  -v "${PWD}/dbt:/dbt" ghcr.io/dbt-labs/dbt-postgres:1.9.0 `
  test --project-dir /dbt/air_quality_dbt --profiles-dir /dbt
```

Hoặc trigger DAG tương ứng trong Airflow UI: `uci_ingest_raw`, `uci_process_raw`, `openmeteo_ingest_raw`, `staging_load`.

## 3) Slice fresh — Wanshouxigong

Chứng minh path không chỉ skip (không xóa MinIO/Postgres toàn cục):

```powershell
# Staging reload 1 trạm (transaction replace-by-station vẫn chạy nếu object resolve được)
py scripts/load_staging.py --station Wanshouxigong
py scripts/verify_staging_load.py --station Wanshouxigong
```

Hoặc Airflow: trigger `staging_load` với conf `{"station":"Wanshouxigong"}`.

## 4) Mining verify (P12d) — không retrain

Trước khi check cluster/predictions, đồng bộ seed + staging predictions với artifact (tránh mart lệch sau `dbt run` trên seed/staging cũ):

```powershell
docker run --rm --network air-quality-network --env-file .env `
  -e POSTGRES_HOST=postgres -e POSTGRES_PORT=5432 `
  -e DBT_SEND_ANONYMOUS_USAGE_STATS=false -e DO_NOT_TRACK=1 `
  -v "${PWD}/dbt:/dbt" ghcr.io/dbt-labs/dbt-postgres:1.9.0 `
  seed --full-refresh --project-dir /dbt/air_quality_dbt --profiles-dir /dbt

py -3 -c "from pathlib import Path; from dotenv import load_dotenv; load_dotenv(Path('.')/'.env'); from src.forecasting.persist import load_predictions_to_staging; print(load_predictions_to_staging())"

docker run --rm --network air-quality-network --env-file .env `
  -e POSTGRES_HOST=postgres -e POSTGRES_PORT=5432 `
  -e DBT_SEND_ANONYMOUS_USAGE_STATS=false -e DO_NOT_TRACK=1 `
  -v "${PWD}/dbt:/dbt" ghcr.io/dbt-labs/dbt-postgres:1.9.0 `
  run --select mart_station_cluster mart_pm25_predictions --project-dir /dbt/air_quality_dbt --profiles-dir /dbt

py scripts/check_mart_cluster.py
py scripts/check_mart_episodes.py
py scripts/check_mart_predictions.py
py scripts/run_olap_checks.py
```

Xác nhận còn trên disk (khi máy local có):

- `artifacts/clustering/`
- `artifacts/forecasting/`
- `models/pm25_forecast/` (nếu đã train trên máy này)

### Recreate mining nếu mart trống (không thuộc smoke P12)

Xem script Phase 9 / 10:

- Clustering: `scripts/run_clustering_phase9.py` (+ seed/dbt theo docs Phase 9)
- Forecasting: `scripts/run_forecasting_phase10b.py` … `phase10e.py` theo [`docs/IMPLEMENTATION_PLAN.md`](../../docs/IMPLEMENTATION_PLAN.md) §17

## 5) Dashboard smoke

```powershell
docker compose up -d postgres dashboard-api
# Nếu UI báo Failed to fetch dù health OK: recreate để nạp CORS regex mới
# docker compose up -d dashboard-api --force-recreate

Invoke-RestMethod http://127.0.0.1:8100/api/health
Invoke-RestMethod http://127.0.0.1:8100/api/health/db
Invoke-RestMethod http://127.0.0.1:8100/api/stations
# + overview/kpis, episodes, predictions/meta, map/snapshot

cd dashboard/web
npm install
npm run dev
# Mở đúng URL Vite (ưu tiên :5180). Dev dùng .env.development → :8100 trực tiếp.
npm run build
```

Evidence target: `dashboard_smoke.json`.

## 6) Hardening notes (P12e)

- Không commit `.env` (được commit: `dashboard/web/.env.development` — không secret)
- Không hard-code path máy cá nhân
- Screenshot demo → Phase 13
- CORS compose: dùng `[0-9]` / `[.]`, không `\\d` / `\\.` trong default env
