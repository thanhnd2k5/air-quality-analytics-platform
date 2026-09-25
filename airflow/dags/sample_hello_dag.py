"""Sample DAG for Phase 2 infra check (P2-24).

Verifies scheduler + LocalExecutor can run a task and that PYTHONPATH
exposes the project `src` package mounted into the container.
"""

from __future__ import annotations

import logging
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

logger = logging.getLogger(__name__)


def _hello() -> str:
    # Confirms ./src is mounted at /opt/airflow/src (P2-21).
    try:
        import src  # noqa: F401

        src_status = "src package importable"
    except ImportError:
        src_status = "src package not on PYTHONPATH (mount check failed)"

    message = f"hello from air-quality-analytics-platform ({src_status})"
    logger.info(message)
    print(message)
    return message


with DAG(
    dag_id="sample_hello",
    description="Phase 2 smoke-test DAG — LocalExecutor + UI",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["sample", "phase2", "infra"],
) as dag:
    PythonOperator(
        task_id="say_hello",
        python_callable=_hello,
    )
