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
