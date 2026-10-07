"""Phase 3 DAG: ingest UCI raw station CSV → MinIO Raw zone.

Manual trigger. Default station = Wanshouxigong (vertical slice).
Pass conf {"station": "<Name>"} or {"stations": ["A", "B"]} for other stations.
"""

from __future__ import annotations

import logging
from datetime import datetime

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


def validate_source(**context) -> list[dict]:
    from src.validation.uci_raw import validate_uci_raw_file

    stations = _stations_from_context(**context)
    results = []
    for station in stations:
        result = validate_uci_raw_file(station)
        payload = {
            "station": result.station,
            "ok": result.ok,
            "source_path": str(result.source_path),
            "file_name": result.file_name,
            "message": result.message,
        }
        logger.info("validate %s: %s", station, payload)
        if not result.ok:
            raise ValueError(result.message)
        results.append(payload)
    return results


def upload_raw(**context) -> list[dict]:
    from src.ingestion.uci_to_minio import ingest_station_to_minio

    stations = _stations_from_context(**context)
    conf = (context.get("dag_run") and context["dag_run"].conf) or {}
    ingestion_date = conf.get("ingestion_date")

    results = []
    for station in stations:
        result = ingest_station_to_minio(station, ingestion_date=ingestion_date)
        payload = result.to_dict()
        logger.info("ingest %s: %s", station, payload)
        results.append(payload)
    return results


with DAG(
    dag_id="uci_ingest_raw",
    description="Phase 3 – UCI CSV → MinIO Raw (validate → upload)",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["phase3", "ingestion", "uci", "minio"],
) as dag:
    validate = PythonOperator(
        task_id="validate_source",
        python_callable=validate_source,
    )
    upload = PythonOperator(
        task_id="upload_raw",
        python_callable=upload_raw,
    )
    validate >> upload
