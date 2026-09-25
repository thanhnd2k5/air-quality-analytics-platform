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

Init once (or after wiping Postgres volume):

```powershell
docker compose up airflow-init
docker compose up -d airflow-webserver airflow-scheduler
```

Sample DAG: `sample_hello` (trigger manually in UI; starts paused).
