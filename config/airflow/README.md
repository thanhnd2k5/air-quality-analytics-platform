# Airflow (Phase 2 – K2-04)

Minimal local setup agreed for this project:

| Item | Choice |
|---|---|
| Image | `apache/airflow:2.10.5` |
| Executor | **LocalExecutor** (no Redis / Celery) |
| Metadata DB | shared Postgres instance, logical DB `airflow_db` |
| Services | `airflow-init`, `airflow-webserver`, `airflow-scheduler` |
| UI | http://localhost:8080 |
| Internal DNS | `postgres:5432`, `minio:9000` (never `localhost` between containers) |

Mounts:

- `airflow/dags` → `/opt/airflow/dags`
- `airflow/logs` → `/opt/airflow/logs`
- `airflow/plugins` → `/opt/airflow/plugins`
- `src` → `/opt/airflow/src` (`PYTHONPATH=/opt/airflow` → `import src`)
- `data/raw` → `/opt/airflow/data/raw` (read-only; Phase 3 UCI ingestion)

MinIO from Airflow tasks (compose injects):

| Variable | In-container value |
|---|---|
| `MINIO_ENDPOINT` | `minio:9000` |
| `MINIO_BUCKET` | from `.env` (`air-quality-lake`) |
| `UCI_RAW_DIR` | `/opt/airflow/data/raw/uci` |
| `UCI_INVENTORY_PATH` | `/opt/airflow/data/raw/reference/file_inventory.csv` |

Host-side CLI smoke uses `MINIO_ENDPOINT=localhost:9000` from `.env`.

Init once (or after wiping Postgres volume):

```powershell
docker compose up airflow-init
docker compose up -d airflow-webserver airflow-scheduler
```

Sample DAG: `sample_hello` (trigger manually in UI; starts paused).

Phase 3 DAG (K3-03+): `uci_ingest_raw` — param `station` (default `Wanshouxigong`).

Phase 4 DAG (K4-03+): `uci_process_raw` — tasks `resolve_raw` → `transform_and_dq` → `write_processed`.

- Default station: `Wanshouxigong`
- Conf: `{"station":"..."}` or `{"stations":[...]}`; optional `{"process_date":"YYYY-MM-DD"}`
- Reads MinIO raw; writes `processed/uci/air_quality/...` (+ sidecar). Does not mutate raw.

Phase 5 DAG: `openmeteo_ingest_raw` — tasks `ingest_raw` → `process_weather`.

- Default station: `Wanshouxigong`; full UCI date range `2013-03-01` → `2017-02-28` (yearly chunks)
- Conf: `{"station":"..."}` / `{"stations":[...]}`; optional `start`, `end`, `ingestion_date`, `process_date`, `process` (bool)
- Writes `raw/openmeteo/historical_weather/...` then `processed/weather/openmeteo/...`
- Process reads only the `ingestion_date` partition from conf, or the latest partition when omitted (does not mix older raw batches)
- Idempotency: raw skip by `request_fingerprint`; processed skip by combined `source_sha256` + `schema_version`

Phase 6 DAG: `staging_load` — tasks `ensure_schema` → `load_station_reference` → `load_air_quality` → `load_openmeteo` → `reconcile`.

- Default station: `Wanshouxigong`
- Conf: `{"station":"..."}` or `{"stations":[...]}`; optional `{"skip_reference": true}`
- Reads latest processed Parquet (not `processed/quarantine/`) and `stations.csv`
- Writes PostgreSQL `staging.*` on `air_quality_dw`. Does not mutate MinIO.
- In-container Postgres is `postgres:5432` (host CLI stays on `POSTGRES_PORT`, usually 5433)
- Idempotency: `staging.load_registry` matches latest object key + `source_sha256` + `schema_version` + `row_count`, and the table still has that many rows → `skipped_identical`. A newer `process_date` reloads.
- Webserver/scheduler pip default upgrades `pyarrow` to `25.0.1` (the image ships 19, which cannot read Parquet written by 25). `pandas` and `psycopg2` come with the Airflow image.
