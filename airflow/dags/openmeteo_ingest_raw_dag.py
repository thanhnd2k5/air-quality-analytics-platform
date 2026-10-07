"""Phase 5b DAG: Open-Meteo Historical Weather → MinIO Raw (+ optional process).

Manual trigger. Default station = Wanshouxigong (vertical slice).
Pass conf:
  {"station": "<Name>"} or {"stations": ["A", "B"]}
  {"start": "2013-03-01", "end": "2017-02-28"}
  {"process": true, "process_date": "YYYY-MM-DD"}
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


def ingest_raw(**context) -> list[dict]:
    from src.ingestion.openmeteo_to_minio import (
        DEFAULT_END_DATE,
        DEFAULT_START_DATE,
        ingest_openmeteo_station_to_minio,
    )

    stations = _stations_from_context(**context)
    conf = (context.get("dag_run") and context["dag_run"].conf) or {}
    start = conf.get("start") or DEFAULT_START_DATE
    end = conf.get("end") or DEFAULT_END_DATE
    ingestion_date = conf.get("ingestion_date")

    results: list[dict] = []
    for station in stations:
        chunk_results = ingest_openmeteo_station_to_minio(
            station,
            start_date=start,
            end_date=end,
            ingestion_date=ingestion_date,
        )
        for r in chunk_results:
            payload = r.to_dict()
            logger.info("openmeteo ingest %s: %s", station, payload.get("status"))
            results.append(payload)
    return results


def process_weather(**context) -> list[dict]:
    from src.processing.openmeteo_to_processed import process_openmeteo_station

    conf = (context.get("dag_run") and context["dag_run"].conf) or {}
    if not conf.get("process", True):
        logger.info("Skipping process_weather (conf.process=false)")
        return []

    stations = _stations_from_context(**context)
    process_date = conf.get("process_date")
    results: list[dict] = []
    for station in stations:
        result = process_openmeteo_station(station, process_date=process_date)
        payload = result.to_dict()
        logger.info("openmeteo process %s: %s", station, payload.get("status"))
        results.append(payload)
    return results


with DAG(
    dag_id="openmeteo_ingest_raw",
    description="Phase 5b – Open-Meteo API → MinIO Raw → processed om_*",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["phase5", "ingestion", "openmeteo", "minio"],
) as dag:
    ingest = PythonOperator(
        task_id="ingest_raw",
        python_callable=ingest_raw,
    )
    process = PythonOperator(
        task_id="process_weather",
        python_callable=process_weather,
    )
    ingest >> process
