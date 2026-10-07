"""Phase 4 DAG: process UCI raw MinIO CSV → Processed Parquet.

Manual trigger. Default station = Wanshouxigong (vertical slice).
Pass conf {"station": "<Name>"} or {"stations": ["A", "B"]} for other stations.
Optional: {"process_date": "YYYY-MM-DD"}.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

from airflow import DAG
from airflow.operators.python import PythonOperator

logger = logging.getLogger(__name__)

DEFAULT_STATION = "Wanshouxigong"


def _stations_from_context(**context) -> list[str]:
    conf = (context.get("dag_run") and context["dag_run"].conf) or {}
    if conf.get("stations"):
        return list(conf["stations"])
    if conf.get("station"):
        return [conf["station"]]
    return [DEFAULT_STATION]


def resolve_raw(**context) -> list[dict]:
    from src.processing.uci_to_processed import resolve_latest_raw_object_key
    from src.utils.minio_client import get_bucket, get_minio_client, get_object_metadata

    stations = _stations_from_context(**context)
    client = get_minio_client()
    bucket = get_bucket()
    results = []
    for station in stations:
        raw_key = resolve_latest_raw_object_key(station, client=client, bucket=bucket)
        meta = get_object_metadata(client, bucket, raw_key)
        payload = {
            "station": station,
            "raw_object_key": raw_key,
            "source_sha256": meta.get("sha256", ""),
        }
        logger.info("resolve_raw %s: %s", station, payload)
        results.append(payload)
    return results


def transform_and_dq(**context) -> list[dict]:
    """Download raw, run canonical transform + DQ (fail-fast before write)."""
    from src.processing.dq import apply_data_quality
    from src.processing.transform import transform_uci_csv_bytes
    from src.utils.minio_client import get_bucket, get_minio_client, get_object_bytes

    ti = context["ti"]
    resolved = ti.xcom_pull(task_ids="resolve_raw")
    process_ts = (
        datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )

    client = get_minio_client()
    bucket = get_bucket()
    results = []
    for item in resolved:
        station = item["station"]
        raw_key = item["raw_object_key"]
        raw_bytes = get_object_bytes(client, bucket, raw_key)
        source_sha = item.get("source_sha256") or hashlib.sha256(raw_bytes).hexdigest()
        canonical = transform_uci_csv_bytes(
            raw_bytes,
            station,
            source_file_name=raw_key.rsplit("/", 1)[-1],
            source_object_key=raw_key,
            source_sha256=source_sha,
            process_time=process_ts,
        )
        dq = apply_data_quality(canonical)
        payload = {
            "station": station,
            "raw_object_key": raw_key,
            "row_count": len(dq.clean),
            "quarantine_row_count": dq.quarantine_row_count,
            "suspect_cap_row_count": dq.suspect_cap_row_count,
            "missing_pollutant_row_count": dq.missing_pollutant_row_count,
            "missing_weather_row_count": dq.missing_weather_row_count,
        }
        logger.info("transform_and_dq %s: %s", station, payload)
        results.append(payload)
    return results


def write_processed(**context) -> list[dict]:
    from src.processing.uci_to_processed import process_station_to_processed

    ti = context["ti"]
    resolved = ti.xcom_pull(task_ids="resolve_raw")
    conf = (context.get("dag_run") and context["dag_run"].conf) or {}
    process_date = conf.get("process_date")

    results = []
    for item in resolved:
        station = item["station"]
        result = process_station_to_processed(
            station,
            process_date=process_date,
            raw_object_key=item["raw_object_key"],
        )
        payload = result.to_dict()
        logger.info("write_processed %s: %s", station, payload)
        results.append(payload)
    return results


with DAG(
    dag_id="uci_process_raw",
    description="Phase 4 – UCI MinIO Raw → Processed Parquet (resolve → DQ → write)",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["phase4", "processing", "uci", "minio"],
) as dag:
    t_resolve = PythonOperator(
        task_id="resolve_raw",
        python_callable=resolve_raw,
    )
    t_dq = PythonOperator(
        task_id="transform_and_dq",
        python_callable=transform_and_dq,
    )
    t_write = PythonOperator(
        task_id="write_processed",
        python_callable=write_processed,
    )
    t_resolve >> t_dq >> t_write
