"""CDC serving + continuous eval (Phase 4 / design §5).

Frozen locked model predicts PM2.5(t+1) from features at origin t only.
When CDC later loads actual at t+1, backfill y_true + abs_error and MAE.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import joblib
import numpy as np
import pandas as pd

from src.forecasting.constants import (
    FEATURE_COLS_V2,
    PM25_LAGS,
    PM25_ROLL_WINDOWS,
    TARGET_COL,
    TRAIN_END,
)
from src.forecasting.features import (
    add_calendar_codes,
    add_causal_episode_features,
    add_pm25_delta,
    add_pm25_lags_and_rolls,
    add_pollutant_lags_and_missing_flags,
    add_weather_lags_and_missing_flags,
    impute_numeric_from_train,
)
from src.forecasting.persist import model_version as locked_model_version
from src.ingestion.db_client import SOURCE_IDENTIFIER
from src.staging.load import connect

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT / "models" / "pm25_forecast" / "model.joblib"
CLUSTER_CSV = ROOT / "artifacts" / "clustering" / "cluster_assignment.csv"
ARTIFACT_DIR = ROOT / "artifacts" / "cdc_eval"
MAE_ARTIFACT = ARTIFACT_DIR / "mae_by_batch.json"

TABLE_PRED = "staging.cdc_prediction_log"
LOOKBACK_HOURS = 48  # need >=24h lags before origin t
# Monitoring flag only (µg/m³). Does not trigger retrain or change the locked model.
MAE_ALERT_THRESHOLD = 12.0

DDL_STATEMENTS = (
    "CREATE SCHEMA IF NOT EXISTS staging",
    f"""
CREATE TABLE IF NOT EXISTS {TABLE_PRED} (
    station_name TEXT NOT NULL,
    station_key INTEGER,
    target_time_local TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    y_hat_pm25 DOUBLE PRECISION NOT NULL,
    y_true_pm25 DOUBLE PRECISION,
    abs_error DOUBLE PRECISION,
    predicted_at_local TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    source_system TEXT NOT NULL DEFAULT 'operational_db',
    model_version TEXT NOT NULL,
    eval_batch_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (station_name, target_time_local, model_version)
)
""".strip(),
    f"CREATE INDEX IF NOT EXISTS idx_cdc_pred_predicted_at ON {TABLE_PRED} (predicted_at_local)",
    f"CREATE INDEX IF NOT EXISTS idx_cdc_pred_eval_batch ON {TABLE_PRED} (eval_batch_id)",
)


@dataclass(frozen=True)
class CdcEvalResult:
    status: str
    predict_rows: int
    backfill_rows: int
    skipped_no_features: int
    skipped_stations: tuple[str, ...]
    eval_batch_id: str | None
    model_version: str
    mae: float | None
    rmse: float | None
    scored_rows: int
    message: str
    artifact_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def ensure_prediction_log(conn=None) -> None:
    own = conn is None
    connection = conn or connect()
    try:
        previous = connection.autocommit
        connection.autocommit = True
        try:
            with connection.cursor() as cur:
                for statement in DDL_STATEMENTS:
                    cur.execute(statement)
        finally:
            connection.autocommit = previous
    finally:
        if own:
            connection.close()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_locked_model(path: Path = MODEL_PATH) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing locked model: {path}")
    blob = joblib.load(path)
    if not isinstance(blob, dict) or "estimator" not in blob:
        raise ValueError(f"Unexpected model artifact shape at {path}")
    return blob


def _month_to_season(month: int) -> str:
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "autumn"


def relative_humidity_pct(temp_c: pd.Series, dew_c: pd.Series) -> pd.Series:
    """Magnus approximation; NaN-safe."""
    t = pd.to_numeric(temp_c, errors="coerce")
    td = pd.to_numeric(dew_c, errors="coerce")
    # e(Td)/e(T) * 100
    a, b = 17.625, 243.04
    with np.errstate(over="ignore", invalid="ignore"):
        rh = 100.0 * np.exp((a * td) / (b + td) - (a * t) / (b + t))
    out = pd.Series(rh, index=t.index)
    return out.clip(lower=0.0, upper=100.0)


def _load_cluster_map() -> pd.DataFrame:
    if not CLUSTER_CSV.is_file():
        raise FileNotFoundError(f"Missing cluster assignment: {CLUSTER_CSV}")
    df = pd.read_csv(CLUSTER_CSV)
    return df[["station_key", "station_name", "cluster_id", "cluster_label"]].copy()


def fetch_staging_history(
    conn,
    *,
    start: str,
    end: str,
) -> pd.DataFrame:
    """Hourly measures from staging (any source_system) for feature lookback."""
    sql = """
        SELECT
            r.station_id AS station_key,
            a.station_name,
            a.event_time_local,
            a.pm25_ug_m3,
            a.pm10_ug_m3,
            a.co_ug_m3,
            a.no2_ug_m3,
            a.temperature_c,
            a.dew_point_c,
            a.wind_speed_m_s,
            a.source_system
        FROM staging.air_quality_hourly a
        INNER JOIN staging.station_reference r
            ON a.station_name = r.station_name
        WHERE a.event_time_local >= %s::timestamp
          AND a.event_time_local <= %s::timestamp
        ORDER BY r.station_id, a.event_time_local
    """
    with conn.cursor() as cur:
        cur.execute(sql, (start, end))
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
    conn.rollback()
    df = pd.DataFrame(rows, columns=cols)
    if df.empty:
        return df
    df["event_time_local"] = pd.to_datetime(df["event_time_local"])
    # Prefer operational_db on duplicate natural keys (not lexical source name order).
    df["_src_prio"] = (df["source_system"] == SOURCE_IDENTIFIER).astype(int)
    df = df.sort_values(
        ["station_key", "event_time_local", "_src_prio"],
        ascending=[True, True, False],
    )
    df = df.drop_duplicates(subset=["station_key", "event_time_local"], keep="first")
    return df.drop(columns=["_src_prio"]).reset_index(drop=True)


def list_new_origin_times(
    conn,
    *,
    watermark_start: str | None,
    watermark_end: str,
) -> pd.DataFrame:
    """Origins t newly present in operational_db staging within (start, end]."""
    if watermark_start:
        sql = """
            SELECT DISTINCT station_name, event_time_local AS predicted_at_local
            FROM staging.air_quality_hourly
            WHERE source_system = %s
              AND event_time_local > %s::timestamp
              AND event_time_local <= %s::timestamp
            ORDER BY event_time_local, station_name
        """
        params = (SOURCE_IDENTIFIER, watermark_start, watermark_end)
    else:
        sql = """
            SELECT DISTINCT station_name, event_time_local AS predicted_at_local
            FROM staging.air_quality_hourly
            WHERE source_system = %s
              AND event_time_local <= %s::timestamp
            ORDER BY event_time_local, station_name
        """
        params = (SOURCE_IDENTIFIER, watermark_end)
    with conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
    conn.rollback()
    df = pd.DataFrame(rows, columns=cols)
    if not df.empty:
        df["predicted_at_local"] = pd.to_datetime(df["predicted_at_local"])
    return df


def build_serve_base(history: pd.DataFrame) -> pd.DataFrame:
    """Attach calendar, RH, cluster — same grain as forecast extract."""
    if history.empty:
        return history
    clusters = _load_cluster_map()
    out = history.merge(clusters, on=["station_key", "station_name"], how="left")
    if out["cluster_id"].isna().any():
        missing = out.loc[out["cluster_id"].isna(), "station_name"].unique().tolist()
        raise ValueError(f"Missing cluster_id for stations: {missing}")
    out["cluster_id"] = out["cluster_id"].astype(int)
    ts = out["event_time_local"]
    out["hour"] = ts.dt.hour.astype(int)
    out["month"] = ts.dt.month.astype(int)
    out["day_of_week"] = ts.dt.dayofweek.astype(int)
    out["season"] = out["month"].map(_month_to_season)
    out["relative_humidity_pct"] = relative_humidity_pct(
        out["temperature_c"], out["dew_point_c"]
    )
    return out


def build_serve_features(base: pd.DataFrame) -> pd.DataFrame:
    """
    Causal features at origin t. Does NOT require y(t+1) present.

    Anti-leakage: never shifts PM2.5 backward from the future into X.
    """
    if base.empty:
        return base
    df = base.sort_values(["station_key", "event_time_local"]).reset_index(drop=True)
    df = add_calendar_codes(df)
    df = add_pm25_lags_and_rolls(df)
    df = add_pm25_delta(df)
    df = add_weather_lags_and_missing_flags(df)
    df = add_pollutant_lags_and_missing_flags(df)
    df = add_causal_episode_features(df)
    # Label split only for train-median impute (≤2015 rows act as train).
    from src.forecasting.split import assign_split

    df["split"] = assign_split(df["event_time_local"])
    # Rows with no train label but need impute: treat as val for fill, medians from train.
    train_mask = df["event_time_local"] <= pd.Timestamp(TRAIN_END)
    df.loc[train_mask, "split"] = "train"
    df.loc[~train_mask & df["split"].isna(), "split"] = "val"

    required = [
        "pm25_ug_m3",
        *(f"pm25_lag_{k}" for k in PM25_LAGS),
        *(f"pm25_roll_mean_{w}" for w in PM25_ROLL_WINDOWS),
    ]
    df = df.dropna(subset=required).reset_index(drop=True)

    weather_pollutant = [
        c
        for c in df.columns
        if not c.endswith("_missing")
        and (
            c
            in {
                "temperature_c",
                "relative_humidity_pct",
                "wind_speed_m_s",
                "pm10_ug_m3",
                "co_ug_m3",
                "no2_ug_m3",
            }
            or c.startswith("temperature_c_lag_")
            or c.startswith("relative_humidity_pct_lag_")
            or c.startswith("wind_speed_m_s_lag_")
            or c.startswith("pm10_ug_m3_lag_")
            or c.startswith("co_ug_m3_lag_")
            or c.startswith("no2_ug_m3_lag_")
        )
    ]
    df, _ = impute_numeric_from_train(df, cols=weather_pollutant)
    return df


def assert_anti_leakage(feature_cols: Sequence[str]) -> None:
    banned = {TARGET_COL, "y_true_pm25", "pm25_tplus1"}
    leak = banned.intersection(feature_cols)
    if leak:
        raise RuntimeError(f"Anti-leakage violation: feature cols include {sorted(leak)}")
    if any("tplus" in c.lower() or "t+1" in c.lower() for c in feature_cols):
        raise RuntimeError(f"Anti-leakage violation: suspicious feature names in {feature_cols}")


def predict_origins(
    features: pd.DataFrame,
    origins: pd.DataFrame,
    *,
    model_blob: dict[str, Any],
) -> pd.DataFrame:
    """Predict y_hat for (station_name, predicted_at_local) origin rows."""
    feature_cols = list(model_blob.get("feature_cols") or FEATURE_COLS_V2)
    assert_anti_leakage(feature_cols)
    estimator = model_blob["estimator"]

    merged = origins.merge(
        features,
        left_on=["station_name", "predicted_at_local"],
        right_on=["station_name", "event_time_local"],
        how="inner",
    )
    if merged.empty:
        return merged

    missing = [c for c in feature_cols if c not in merged.columns]
    if missing:
        raise KeyError(f"Missing feature columns for serve: {missing}")

    x = merged.loc[:, feature_cols]
    y_hat = estimator.predict(x)
    out = pd.DataFrame(
        {
            "station_name": merged["station_name"].astype(str),
            "station_key": merged["station_key"].astype(int),
            "predicted_at_local": pd.to_datetime(merged["predicted_at_local"]),
            "target_time_local": pd.to_datetime(merged["predicted_at_local"])
            + pd.Timedelta(hours=1),
            "y_hat_pm25": np.asarray(y_hat, dtype=float),
        }
    )
    return out.reset_index(drop=True)


def _to_naive_timestamp(value: Any) -> datetime:
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
    if getattr(value, "tzinfo", None) is not None:
        return value.replace(tzinfo=None)
    return value


def upsert_predictions(
    conn,
    preds: pd.DataFrame,
    *,
    model_version: str,
    eval_batch_id: str,
) -> int:
    """Insert new predictions. Do not overwrite y_hat once y_true is scored."""
    if preds.empty:
        return 0
    rows = [
        (
            str(r.station_name),
            int(r.station_key),
            _to_naive_timestamp(r.target_time_local),
            float(r.y_hat_pm25),
            _to_naive_timestamp(r.predicted_at_local),
            SOURCE_IDENTIFIER,
            model_version,
            eval_batch_id,
        )
        for r in preds.itertuples(index=False)
    ]
    # Unscored rows: refresh y_hat / lineage. Scored rows: keep y_hat/y_true/abs_error.
    sql = f"""
        INSERT INTO {TABLE_PRED} (
            station_name, station_key, target_time_local, y_hat_pm25,
            predicted_at_local, source_system, model_version, eval_batch_id
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (station_name, target_time_local, model_version) DO UPDATE SET
            y_hat_pm25 = EXCLUDED.y_hat_pm25,
            predicted_at_local = EXCLUDED.predicted_at_local,
            station_key = EXCLUDED.station_key,
            eval_batch_id = COALESCE(EXCLUDED.eval_batch_id, {TABLE_PRED}.eval_batch_id),
            source_system = EXCLUDED.source_system
        WHERE {TABLE_PRED}.y_true_pm25 IS NULL
    """
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
    conn.commit()
    return len(rows)


def backfill_actuals(conn) -> int:
    """Fill y_true + abs_error when operational_db actual at target_time exists."""
    sql = f"""
        UPDATE {TABLE_PRED} AS p
        SET
            y_true_pm25 = a.pm25_ug_m3,
            abs_error = ABS(p.y_hat_pm25 - a.pm25_ug_m3)
        FROM staging.air_quality_hourly AS a
        WHERE a.station_name = p.station_name
          AND a.event_time_local = p.target_time_local
          AND a.source_system = %s
          AND a.pm25_ug_m3 IS NOT NULL
          AND p.y_true_pm25 IS NULL
    """
    with conn.cursor() as cur:
        cur.execute(sql, (SOURCE_IDENTIFIER,))
        n = cur.rowcount
    conn.commit()
    return int(n)


def compute_mae_snapshot(conn) -> dict[str, Any]:
    sql = f"""
        SELECT
            eval_batch_id,
            COUNT(*) FILTER (WHERE y_true_pm25 IS NOT NULL) AS scored_n,
            AVG(abs_error) FILTER (WHERE abs_error IS NOT NULL) AS mae,
            SQRT(AVG(abs_error * abs_error) FILTER (WHERE abs_error IS NOT NULL)) AS rmse,
            MIN(predicted_at_local) AS min_predicted_at,
            MAX(predicted_at_local) AS max_predicted_at,
            MIN(target_time_local) FILTER (WHERE y_true_pm25 IS NOT NULL) AS min_scored_target,
            MAX(target_time_local) FILTER (WHERE y_true_pm25 IS NOT NULL) AS max_scored_target
        FROM {TABLE_PRED}
        GROUP BY eval_batch_id
        ORDER BY max_predicted_at NULLS LAST
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    conn.rollback()

    overall_sql = f"""
        SELECT
            COUNT(*) FILTER (WHERE y_true_pm25 IS NOT NULL) AS scored_n,
            AVG(abs_error) FILTER (WHERE abs_error IS NOT NULL) AS mae,
            SQRT(AVG(abs_error * abs_error) FILTER (WHERE abs_error IS NOT NULL)) AS rmse
        FROM {TABLE_PRED}
    """
    with conn.cursor() as cur:
        cur.execute(overall_sql)
        overall = dict(zip([d[0] for d in cur.description], cur.fetchone()))
    conn.rollback()

    def _ser(v: Any) -> Any:
        if v is None:
            return None
        if hasattr(v, "isoformat"):
            return v.isoformat(sep=" ")
        if isinstance(v, float):
            return None if np.isnan(v) else float(v)
        return v

    def _annotate(row: dict[str, Any]) -> dict[str, Any]:
        out = {k: _ser(v) for k, v in row.items()}
        mae = out.get("mae")
        out["mae_alert_threshold"] = MAE_ALERT_THRESHOLD
        out["mae_above_threshold"] = (
            bool(mae is not None and float(mae) > MAE_ALERT_THRESHOLD)
        )
        return out

    batches = [_annotate(row) for row in rows]
    overall_out = _annotate(overall)
    return {
        "updated_at": _utc_now_iso(),
        "policy": {
            "mae_alert_threshold": MAE_ALERT_THRESHOLD,
            "action_when_above": "monitor_only",
            "note": (
                "Batch MAE above threshold is a monitoring signal only. "
                "Model weights stay frozen; retraining is an offline process "
                "outside this CDC evaluation loop."
            ),
        },
        "overall": overall_out,
        "by_batch": batches,
    }


def write_mae_artifact(snapshot: dict[str, Any], path: Path = MAE_ARTIFACT) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return path


def run_cdc_eval(
    *,
    watermark_start: str | None,
    watermark_end: str,
    eval_batch_id: str | None = None,
    conn=None,
    model_path: Path = MODEL_PATH,
) -> CdcEvalResult:
    """
    1) Predict for new operational origins in (watermark_start, watermark_end]
    2) Backfill actuals for any pending targets now present
    3) Write MAE artifact
    """
    own = conn is None
    connection = conn or connect()
    batch_id = eval_batch_id or f"wm_{watermark_end.replace(' ', 'T').replace(':', '')}"
    try:
        ensure_prediction_log(connection)
        model_blob = load_locked_model(model_path)
        version = locked_model_version()

        origins = list_new_origin_times(
            connection,
            watermark_start=watermark_start,
            watermark_end=watermark_end,
        )
        if origins.empty:
            backfilled = backfill_actuals(connection)
            snap = compute_mae_snapshot(connection)
            art = write_mae_artifact(snap)
            overall = snap["overall"]
            return CdcEvalResult(
                status="empty_origins",
                predict_rows=0,
                backfill_rows=backfilled,
                skipped_no_features=0,
                skipped_stations=(),
                eval_batch_id=batch_id,
                model_version=version,
                mae=overall.get("mae"),
                rmse=overall.get("rmse"),
                scored_rows=int(overall.get("scored_n") or 0),
                message="no new operational_db origins to predict",
                artifact_path=str(art),
            )

        t_min = origins["predicted_at_local"].min() - pd.Timedelta(hours=LOOKBACK_HOURS)
        t_max = origins["predicted_at_local"].max()
        history = fetch_staging_history(
            connection,
            start=t_min.strftime("%Y-%m-%d %H:%M:%S"),
            end=t_max.strftime("%Y-%m-%d %H:%M:%S"),
        )
        base = build_serve_base(history)
        features = build_serve_features(base)
        preds = predict_origins(features, origins, model_blob=model_blob)

        def _origin_key(frame: pd.DataFrame, time_col: str) -> pd.Series:
            return (
                frame["station_name"].astype(str)
                + "|"
                + pd.to_datetime(frame[time_col]).dt.strftime("%Y-%m-%d %H:%M:%S")
            )

        predicted_keys = (
            set(_origin_key(preds, "predicted_at_local")) if not preds.empty else set()
        )
        origin_keys = _origin_key(origins, "predicted_at_local")
        skipped_rows = origins.loc[~origin_keys.isin(predicted_keys)]
        skipped = int(len(skipped_rows))
        skipped_stations = tuple(
            sorted(skipped_rows["station_name"].astype(str).unique().tolist())
        )
        if skipped:
            logger.warning(
                "cdc_serve skipped %s origins (insufficient lag/features); stations=%s",
                skipped,
                list(skipped_stations),
            )

        n_pred = upsert_predictions(
            connection,
            preds,
            model_version=version,
            eval_batch_id=batch_id,
        )
        n_back = backfill_actuals(connection)
        snap = compute_mae_snapshot(connection)
        art = write_mae_artifact(snap)
        overall = snap["overall"]
        return CdcEvalResult(
            status="ok",
            predict_rows=n_pred,
            backfill_rows=n_back,
            skipped_no_features=skipped,
            skipped_stations=skipped_stations,
            eval_batch_id=batch_id,
            model_version=version,
            mae=overall.get("mae"),
            rmse=overall.get("rmse"),
            scored_rows=int(overall.get("scored_n") or 0),
            message="predicted new origins, backfilled actuals, wrote MAE artifact",
            artifact_path=str(art),
        )
    finally:
        if own:
            connection.close()
