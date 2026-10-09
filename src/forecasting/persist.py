"""Load locked predictions into staging for dbt mart (Phase 10d)."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.staging.load import connect

ROOT = Path(__file__).resolve().parents[2]
PRED_PATH = ROOT / "artifacts" / "forecasting" / "predictions_locked.parquet"
PRED_CSV = ROOT / "artifacts" / "forecasting" / "predictions_locked.csv"
LOCK_PATH = ROOT / "artifacts" / "forecasting" / "model_lock.json"
META_PATH = ROOT / "models" / "pm25_forecast" / "metadata.json"

RAW_TABLE = "staging.pm25_predictions_raw"

DDL = """
create schema if not exists staging;

create table if not exists staging.pm25_predictions_raw (
    station_key integer not null,
    prediction_origin_time timestamp not null,
    target_time timestamp not null,
    split text not null,
    actual_pm25 double precision not null,
    predicted_pm25 double precision not null,
    predicted_pm25_persistence double precision,
    absolute_error double precision not null,
    model_version text not null,
    cluster_id integer,
    primary key (station_key, prediction_origin_time)
);
"""


def _model_version() -> str:
    if META_PATH.is_file():
        meta = json.loads(META_PATH.read_text(encoding="utf-8"))
        name = meta.get("model_name", "unknown")
        created = meta.get("created_at", "")
        return f"{name}@{created}" if created else str(name)
    if LOCK_PATH.is_file():
        lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        return str(lock.get("locked_model", "unknown"))
    return "unknown"


def load_predictions_frame() -> pd.DataFrame:
    if PRED_PATH.is_file():
        df = pd.read_parquet(PRED_PATH)
    elif PRED_CSV.is_file():
        df = pd.read_csv(PRED_CSV)
        df["event_time_local"] = pd.to_datetime(df["event_time_local"])
        df["target_time_local"] = pd.to_datetime(df["target_time_local"])
    else:
        raise FileNotFoundError(
            "Missing predictions_locked.parquet/csv — run scripts/run_forecasting_phase10c.py"
        )

    version = _model_version()
    out = pd.DataFrame(
        {
            "station_key": df["station_key"].astype(int),
            "prediction_origin_time": pd.to_datetime(df["event_time_local"]),
            "target_time": pd.to_datetime(df["target_time_local"]),
            "split": df["split"].astype(str),
            "actual_pm25": df["y_pm25_tplus1"].astype(float),
            "predicted_pm25": df["y_hat_locked"].astype(float),
            "predicted_pm25_persistence": df["y_hat_persistence"].astype(float),
            "absolute_error": df["abs_error_locked"].astype(float),
            "model_version": version,
            "cluster_id": df["cluster_id"].astype(int),
        }
    )
    # Deduplicate grain just in case
    out = out.drop_duplicates(subset=["station_key", "prediction_origin_time"], keep="last")
    return out.reset_index(drop=True)


def _copy_buffer(df: pd.DataFrame) -> io.StringIO:
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False, na_rep="", quoting=csv.QUOTE_MINIMAL)
    buf.seek(0)
    return buf


def load_predictions_to_staging(conn=None) -> dict[str, Any]:
    """TRUNCATE + COPY predictions into staging.pm25_predictions_raw."""
    df = load_predictions_frame()
    owned = False
    if conn is None:
        conn = connect()
        owned = True
    try:
        with conn.cursor() as cur:
            cur.execute(DDL)
            cur.execute(f"truncate table {RAW_TABLE}")
            cols = (
                "station_key, prediction_origin_time, target_time, split, "
                "actual_pm25, predicted_pm25, predicted_pm25_persistence, "
                "absolute_error, model_version, cluster_id"
            )
            cur.copy_expert(
                f"COPY {RAW_TABLE} ({cols}) FROM STDIN WITH (FORMAT csv, NULL '')",
                _copy_buffer(df),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if owned:
            conn.close()

    return {
        "table": RAW_TABLE,
        "row_count": int(len(df)),
        "model_version": str(df["model_version"].iloc[0]) if len(df) else None,
        "split_counts": df["split"].value_counts().to_dict(),
        "stations": int(df["station_key"].nunique()),
    }
