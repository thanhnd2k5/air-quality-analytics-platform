"""Phase 3 DAG: operational SQLite watermark CDC → MinIO Raw → staging.

Manual trigger.

Pass conf (all optional):
  {
    "watermark": "2015-12-31 23:00:00",
    "batch_size": 5000,
    "max_batches": 1,
    "persist_watermark": false,
    "load_staging": true,
    "watermark_from_staging": false,
    "cdc_eval": true
  }

Watermark resolution order:
  conf.watermark → (if watermark_from_staging) staging MAX → Variable → default.
"""

from __future__ import annotations

import logging
from datetime import datetime

from airflow import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator

logger = logging.getLogger(__name__)

VARIABLE_WATERMARK = "operational_db_watermark"


def _conf(**context) -> dict:
    return (context.get("dag_run") and context["dag_run"].conf) or {}


def _resolve_watermark(**context) -> str:
    from src.ingestion.db_client import DEFAULT_WATERMARK, validate_watermark

    conf = _conf(**context)
    if conf.get("watermark"):
        return validate_watermark(str(conf["watermark"]))
    if conf.get("watermark_from_staging"):
        from src.staging.operational_db_load import staging_operational_watermark

        return validate_watermark(staging_operational_watermark())
    stored = Variable.get(VARIABLE_WATERMARK, default_var=DEFAULT_WATERMARK)
    return validate_watermark(str(stored))


def check_source(**context) -> dict:
    """Verify operational SQLite is mounted and readable."""
    from src.ingestion.db_client import (
        DEFAULT_BATCH_SIZE,
        resolve_db_path,
        peek_max_event_time,
    )

    conf = _conf(**context)
    path = resolve_db_path()
    db_max = peek_max_event_time(path)
    watermark = _resolve_watermark(**context)
    batch_size = int(conf.get("batch_size") or DEFAULT_BATCH_SIZE)
    max_batches = int(conf.get("max_batches") or 1)
    load_staging = bool(conf.get("load_staging", True))
    if batch_size < 1:
        raise ValueError(f"batch_size must be >= 1, got {batch_size}")
    if max_batches < 1:
        raise ValueError(f"max_batches must be >= 1, got {max_batches}")

    payload = {
        "ok": True,
        "db_path": str(path),
        "db_max_event_time": db_max,
        "watermark": watermark,
        "batch_size": batch_size,
        "max_batches": max_batches,
        "persist_watermark": bool(conf.get("persist_watermark", False)),
        "load_staging": load_staging,
        "cdc_eval": bool(conf.get("cdc_eval", True)),
    }
    logger.info("operational_db check_source: %s", payload)
    if db_max is None:
        raise RuntimeError(f"operational DB has no rows: {path}")
    return payload


def ingest_delta_batches(**context) -> list[dict]:
    """Fetch one or more CDC batches and upload each to MinIO Raw."""
    from src.ingestion.db_client import fetch_delta
    from src.ingestion.db_to_minio import ingest_delta_batch_to_minio

    ti = context["ti"]
    check = ti.xcom_pull(task_ids="check_source") or {}
    watermark = str(check.get("watermark") or _resolve_watermark(**context))
    batch_size = int(check.get("batch_size") or 5000)
    max_batches = int(check.get("max_batches") or 1)
    persist = bool(check.get("persist_watermark", False))

    results: list[dict] = []
    current_wm = watermark

    for i in range(max_batches):
        batch = fetch_delta(current_wm, batch_size=batch_size)
        result = ingest_delta_batch_to_minio(
            watermark=current_wm,
            batch_size=batch_size,
            batch=batch,
        )
        payload = result.to_dict()
        payload["batch_index"] = i
        logger.info(
            "operational_db ingest batch=%s status=%s count=%s wm_end=%s",
            i,
            result.status,
            result.record_count,
            result.watermark_end,
        )
        results.append(payload)

        if result.status == "empty" or result.watermark_end is None:
            break

        current_wm = result.watermark_end
        if persist:
            Variable.set(VARIABLE_WATERMARK, current_wm)
            logger.info("persisted Variable %s=%s", VARIABLE_WATERMARK, current_wm)

    return results


def load_staging_batches(**context) -> list[dict]:
    """Upsert MinIO CDC batches from this run into staging.air_quality_hourly."""
    ti = context["ti"]
    check = ti.xcom_pull(task_ids="check_source") or {}
    if not bool(check.get("load_staging", True)):
        logger.info("Skipping load_staging_batches (load_staging=false)")
        return [{"status": "skipped_conf", "message": "load_staging=false"}]

    ingest_results = ti.xcom_pull(task_ids="ingest_delta_batches") or []
    object_keys = [
        r["object_key"]
        for r in ingest_results
        if r.get("object_key") and r.get("status") in {"uploaded", "skipped_identical"}
    ]

    from src.staging.operational_db_load import load_cdc_batches, staging_operational_watermark

    if not object_keys:
        payload = {
            "status": "empty",
            "message": "no CDC object keys from ingest",
            "staging_watermark": staging_operational_watermark(),
        }
        logger.info("load_staging_batches %s", payload)
        return [payload]

    results = load_cdc_batches(object_keys)
    out = [r.to_dict() for r in results]
    quarantined = sum(int(r.quarantine_rows) for r in results)
    if quarantined:
        logger.warning(
            "load_staging_batches dropped quarantine_rows=%s across %s batch(es)",
            quarantined,
            len(results),
        )
    logger.info(
        "load_staging_batches loaded=%s skipped=%s empty=%s quarantine_rows=%s wm=%s",
        sum(1 for r in results if r.status == "loaded"),
        sum(1 for r in results if r.status == "skipped_identical"),
        sum(1 for r in results if r.status == "empty"),
        quarantined,
        staging_operational_watermark(),
    )
    return out


def cdc_serve_and_eval(**context) -> dict:
    """Predict PM2.5(t+1) for new CDC origins; backfill actuals; write MAE artifact.

    Evaluates each loaded CDC batch separately so catch-up runs (max_batches>1)
    stay memory-safe and produce per-batch MAE rows.
    """
    ti = context["ti"]
    check = ti.xcom_pull(task_ids="check_source") or {}
    if not bool(check.get("cdc_eval", True)):
        logger.info("Skipping cdc_serve_and_eval (cdc_eval=false)")
        return {"status": "skipped_conf", "message": "cdc_eval=false"}

    load_results = [
        r
        for r in (ti.xcom_pull(task_ids="load_staging_batches") or [])
        if isinstance(r, dict) and r.get("status") in {"loaded", "skipped_identical"}
        and r.get("watermark_end")
    ]

    def _safe(ts: str) -> str:
        return ts.replace(" ", "T").replace(":", "")

    from src.forecasting.cdc_serve import run_cdc_eval

    if not load_results:
        from src.staging.operational_db_load import staging_operational_watermark

        wm_end = staging_operational_watermark()
        wm_start = check.get("watermark")
        batch_id = f"wm_{_safe(str(wm_start or 'none'))}_to_{_safe(str(wm_end))}"
        result = run_cdc_eval(
            watermark_start=str(wm_start) if wm_start else None,
            watermark_end=str(wm_end),
            eval_batch_id=batch_id,
        )
        payload = result.to_dict()
        logger.info(
            "cdc_serve_and_eval status=%s predict=%s backfill=%s mae=%s",
            result.status,
            result.predict_rows,
            result.backfill_rows,
            result.mae,
        )
        return payload

    batch_payloads: list[dict] = []
    total_predict = 0
    total_backfill = 0
    last_mae = None
    for r in load_results:
        wm_start = r.get("watermark_start") or check.get("watermark")
        wm_end = r["watermark_end"]
        batch_id = f"wm_{_safe(str(wm_start or 'none'))}_to_{_safe(str(wm_end))}"
        result = run_cdc_eval(
            watermark_start=str(wm_start) if wm_start else None,
            watermark_end=str(wm_end),
            eval_batch_id=batch_id,
        )
        batch_payloads.append(result.to_dict())
        total_predict += int(result.predict_rows)
        total_backfill += int(result.backfill_rows)
        last_mae = result.mae
        logger.info(
            "cdc_serve_and_eval batch=%s status=%s predict=%s backfill=%s mae=%s",
            batch_id,
            result.status,
            result.predict_rows,
            result.backfill_rows,
            result.mae,
        )

    return {
        "status": "ok",
        "batches": len(batch_payloads),
        "predict_rows": total_predict,
        "backfill_rows": total_backfill,
        "mae": last_mae,
        "batch_results": batch_payloads,
    }


with DAG(
    dag_id="operational_db_cdc",
    description="Phase 3+4 - Operational SQLite CDC -> MinIO -> staging -> CDC eval",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["phase3", "phase4", "ingestion", "operational_db", "cdc", "minio", "staging", "ml"],
) as dag:
    check = PythonOperator(
        task_id="check_source",
        python_callable=check_source,
    )
    ingest = PythonOperator(
        task_id="ingest_delta_batches",
        python_callable=ingest_delta_batches,
    )
    load_staging = PythonOperator(
        task_id="load_staging_batches",
        python_callable=load_staging_batches,
    )
    cdc_eval = PythonOperator(
        task_id="cdc_serve_and_eval",
        python_callable=cdc_serve_and_eval,
    )
    check >> ingest >> load_staging >> cdc_eval
