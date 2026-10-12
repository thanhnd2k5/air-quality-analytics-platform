"""Load locked alert predictions into staging for the dbt mart (mart_pm25_alerts)."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.staging.load import connect

ROOT = Path(__file__).resolve().parents[2]
PRED_PATH = ROOT / "artifacts" / "classification" / "predictions.parquet"
META_PATH = ROOT / "models" / "pm25_alert" / "metadata.json"

RAW_TABLE = "staging.pm25_alert_predictions_raw"

DDL = """
create schema if not exists staging;

create table if not exists staging.pm25_alert_predictions_raw (
    station_key integer not null,
    prediction_origin_time timestamp not null,
    target_time timestamp not null,
    split text not null,
    pm25_at_origin double precision not null,
    actual_pm25 double precision not null,
    actual_alert smallint not null,
    predicted_alert smallint not null,
    predicted_proba double precision not null,
    persistence_alert smallint not null,
    alert_threshold double precision not null,
    probability_cutoff double precision not null,
    model_version text not null,
    cluster_id integer,
    primary key (station_key, prediction_origin_time)
);
"""

COLUMNS = (
    "station_key",
    "prediction_origin_time",
    "target_time",
    "split",
    "pm25_at_origin",
    "actual_pm25",
    "actual_alert",
    "predicted_alert",
    "predicted_proba",
    "persistence_alert",
    "alert_threshold",
    "probability_cutoff",
    "model_version",
    "cluster_id",
)


def _model_version() -> str:
    if not META_PATH.is_file():
        return "unknown"
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    name = meta.get("model_name", "unknown")
    created = meta.get("created_at", "")
    return f"{name}@{created}" if created else str(name)


def load_alert_frame() -> pd.DataFrame:
    if not PRED_PATH.is_file():
        raise FileNotFoundError(
            "Missing artifacts/classification/predictions.parquet — run scripts/run_classification.py"
        )
    df = pd.read_parquet(PRED_PATH)
    out = pd.DataFrame(
        {
            "station_key": df["station_key"].astype(int),
            "prediction_origin_time": pd.to_datetime(df["event_time_local"]),
            "target_time": pd.to_datetime(df["target_time_local"]),
            "split": df["split"].astype(str),
            "pm25_at_origin": df["pm25_ug_m3"].astype(float),
            "actual_pm25": df["y_pm25_target"].astype(float),
            "actual_alert": df["y_alert"].astype(int),
            "predicted_alert": df["pred_locked"].astype(int),
            "predicted_proba": df["proba_locked"].astype(float),
            "persistence_alert": df["pred_persistence"].astype(int),
            "alert_threshold": df["alert_threshold"].astype(float),
            "probability_cutoff": df["probability_cutoff"].astype(float),
            "model_version": _model_version(),
            "cluster_id": df["cluster_id"].astype(int),
        }
    )
    out = out.drop_duplicates(subset=["station_key", "prediction_origin_time"], keep="last")
    return out.loc[:, list(COLUMNS)].reset_index(drop=True)


def load_alerts_to_staging(conn=None) -> dict[str, Any]:
    """TRUNCATE + COPY into staging.pm25_alert_predictions_raw."""
    df = load_alert_frame()
    owned = conn is None
    if owned:
        conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(DDL)
            cur.execute(f"truncate table {RAW_TABLE}")
            buf = io.StringIO()
            df.to_csv(buf, index=False, header=False, na_rep="", quoting=csv.QUOTE_MINIMAL)
            buf.seek(0)
            cur.copy_expert(
                f"COPY {RAW_TABLE} ({', '.join(COLUMNS)}) FROM STDIN WITH (FORMAT csv, NULL '')",
                buf,
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
