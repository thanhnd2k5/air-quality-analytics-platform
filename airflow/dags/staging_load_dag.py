"""Phase 6 DAG: processed Parquet + station reference → PostgreSQL staging.

Manual trigger. Default station = Wanshouxigong.
Pass conf {"station": "<Name>"} or {"stations": ["A", "B"]}.
Optional: {"skip_reference": true}.
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


def _skip_reference(**context) -> bool:
    conf = (context.get("dag_run") and context["dag_run"].conf) or {}
    return bool(conf.get("skip_reference"))


def ensure_schema(**context) -> dict:
    from src.staging.load import apply_ddl, connect

    conn = connect()
    try:
        apply_ddl(conn)
    finally:
        conn.close()
    logger.info("ensure_schema applied staging DDL")
    return {"status": "applied"}


def load_station_reference(**context) -> dict:
    from src.staging.load import load_station_reference

    if _skip_reference(**context):
        payload = {"status": "skipped_conf", "dataset": "station_reference"}
        logger.info("load_station_reference %s", payload)
        return payload
    result = load_station_reference()
    payload = result.to_dict()
    logger.info("load_station_reference %s", payload)
    return payload


def load_air_quality(**context) -> list[dict]:
    from src.staging.load import connect, load_air_quality_station

    conn = connect()
    results = []
    try:
        for station in _stations_from_context(**context):
            result = load_air_quality_station(station, conn, apply_schema=False)
            payload = result.to_dict()
            logger.info("load_air_quality %s", payload)
            results.append(payload)
    finally:
        conn.close()
    return results


def load_openmeteo(**context) -> list[dict]:
    from src.staging.load import connect, load_openmeteo_station

    conn = connect()
    results = []
    try:
        for station in _stations_from_context(**context):
            result = load_openmeteo_station(station, conn, apply_schema=False)
            payload = result.to_dict()
            logger.info("load_openmeteo %s", payload)
            results.append(payload)
    finally:
        conn.close()
    return results


def reconcile_staging(**context) -> dict:
    from src.reference.stations import list_station_names
    from src.staging.load import connect
    from src.staging.reconcile import reconcile
    from src.staging.schema import EXPECTED_STATION_COUNT

    stations = _stations_from_context(**context)
    expect_full = len(stations) >= EXPECTED_STATION_COUNT
    if expect_full:
        stations = list_station_names()
    conn = connect()
    try:
        report = reconcile(conn, stations, expect_full=expect_full)
    finally:
        conn.close()
    logger.info(
        "reconcile ok=%s errors=%s air=%s om=%s",
        report["ok"],
        report["errors"],
        report["air_quality_hourly"]["target_row_count"],
        report["weather_openmeteo_hourly"]["target_row_count"],
    )
    if not report["ok"]:
        raise RuntimeError("; ".join(report["errors"]))
    return {
        "ok": True,
        "air_target": report["air_quality_hourly"]["target_row_count"],
        "om_target": report["weather_openmeteo_hourly"]["target_row_count"],
        "reference_target": report["station_reference"]["target_row_count"],
    }


with DAG(
    dag_id="staging_load",
    description="Phase 6 – processed Parquet + stations.csv → PostgreSQL staging",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["phase6", "staging", "postgres"],
) as dag:
    t_schema = PythonOperator(task_id="ensure_schema", python_callable=ensure_schema)
    t_reference = PythonOperator(
        task_id="load_station_reference",
        python_callable=load_station_reference,
    )
    t_air = PythonOperator(task_id="load_air_quality", python_callable=load_air_quality)
    t_om = PythonOperator(task_id="load_openmeteo", python_callable=load_openmeteo)
    t_reconcile = PythonOperator(task_id="reconcile", python_callable=reconcile_staging)
    t_schema >> t_reference >> t_air >> t_om >> t_reconcile
