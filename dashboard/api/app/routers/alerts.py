"""PM2.5 exceedance alerts (main mining task): confusion matrices + alert timeline."""

from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.coerce import as_float
from app.db import fetch_all, fetch_one, get_db
from app.errors import EmptyMartError
from app.schemas.alerts import (
    AlertMeta,
    AlertPoint,
    AlertSummary,
    AlertTimeline,
    ConfusionMatrix,
    StationAlertMetrics,
)

router = APIRouter(prefix="/alerts", tags=["alerts"])

SplitFilter = Literal["train", "val", "test"]


def _ratio(num: int, den: int) -> float | None:
    return num / den if den else None


def _matrix(tp: int, fp: int, fn: int, tn: int, onsets: int, detected: int) -> ConfusionMatrix:
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and (precision + recall) > 0
        else None
    )
    return ConfusionMatrix(
        tp=tp, fp=fp, fn=fn, tn=tn,
        accuracy=_ratio(tp + tn, tp + fp + fn + tn),
        precision=precision, recall=recall, f1=f1,
        onsets=onsets, onsets_detected=detected,
    )


def _f1(tp: int, fp: int, fn: int) -> float | None:
    return _ratio(2 * tp, 2 * tp + fp + fn)


@router.get("/meta", response_model=AlertMeta)
def alerts_meta(db: Session = Depends(get_db)) -> AlertMeta:
    row = fetch_one(
        db,
        """
        SELECT MIN(target_time)::date AS min_day, MAX(target_time)::date AS max_day
        FROM mart.mart_pm25_alerts
        WHERE split = 'test'
        """,
    )
    if not row or row["min_day"] is None:
        raise EmptyMartError("mart.mart_pm25_alerts is empty")
    end = row["max_day"]
    return AlertMeta(
        data_min=row["min_day"],
        data_max=end,
        default_from=end - timedelta(days=6),
        default_to=end,
    )


@router.get("/summary", response_model=AlertSummary)
def alerts_summary(
    db: Session = Depends(get_db),
    split: SplitFilter = Query("test"),
) -> AlertSummary:
    row = fetch_one(
        db,
        """
        SELECT
            COUNT(*)::int AS n,
            MAX(model_version) AS model_version,
            MAX(alert_threshold) AS alert_threshold,
            MAX(probability_cutoff) AS probability_cutoff,
            COUNT(*) FILTER (WHERE outcome = 'TP')::int AS m_tp,
            COUNT(*) FILTER (WHERE outcome = 'FP')::int AS m_fp,
            COUNT(*) FILTER (WHERE outcome = 'FN')::int AS m_fn,
            COUNT(*) FILTER (WHERE outcome = 'TN')::int AS m_tn,
            COUNT(*) FILTER (WHERE persistence_outcome = 'TP')::int AS p_tp,
            COUNT(*) FILTER (WHERE persistence_outcome = 'FP')::int AS p_fp,
            COUNT(*) FILTER (WHERE persistence_outcome = 'FN')::int AS p_fn,
            COUNT(*) FILTER (WHERE persistence_outcome = 'TN')::int AS p_tn,
            COUNT(*) FILTER (WHERE is_onset)::int AS onsets,
            COUNT(*) FILTER (WHERE is_onset AND predicted_alert = 1)::int AS m_onset_hit,
            COUNT(*) FILTER (WHERE is_onset AND persistence_alert = 1)::int AS p_onset_hit
        FROM mart.mart_pm25_alerts
        WHERE split = :split
        """,
        {"split": split},
    )
    if not row or not row["n"]:
        raise EmptyMartError("mart.mart_pm25_alerts is empty")

    stations = fetch_all(
        db,
        """
        SELECT
            station_key,
            MAX(station_name) AS station_name,
            COUNT(*) FILTER (WHERE actual_alert = 1)::int AS positives,
            COUNT(*) FILTER (WHERE outcome = 'TP')::int AS m_tp,
            COUNT(*) FILTER (WHERE outcome = 'FP')::int AS m_fp,
            COUNT(*) FILTER (WHERE outcome = 'FN')::int AS m_fn,
            COUNT(*) FILTER (WHERE persistence_outcome = 'TP')::int AS p_tp,
            COUNT(*) FILTER (WHERE persistence_outcome = 'FP')::int AS p_fp,
            COUNT(*) FILTER (WHERE persistence_outcome = 'FN')::int AS p_fn
        FROM mart.mart_pm25_alerts
        WHERE split = :split
        GROUP BY station_key
        ORDER BY station_key
        """,
        {"split": split},
    )

    return AlertSummary(
        split=split,
        model_version=row["model_version"],
        alert_threshold=as_float(row["alert_threshold"]),
        probability_cutoff=as_float(row["probability_cutoff"]),
        n=row["n"],
        model=_matrix(row["m_tp"], row["m_fp"], row["m_fn"], row["m_tn"], row["onsets"], row["m_onset_hit"]),
        persistence=_matrix(
            row["p_tp"], row["p_fp"], row["p_fn"], row["p_tn"], row["onsets"], row["p_onset_hit"]
        ),
        stations=[
            StationAlertMetrics(
                station_key=s["station_key"],
                station_name=s["station_name"],
                positives=s["positives"],
                f1_model=_f1(s["m_tp"], s["m_fp"], s["m_fn"]),
                f1_persistence=_f1(s["p_tp"], s["p_fp"], s["p_fn"]),
                recall_model=_ratio(s["m_tp"], s["m_tp"] + s["m_fn"]),
                recall_persistence=_ratio(s["p_tp"], s["p_tp"] + s["p_fn"]),
            )
            for s in stations
        ],
    )


@router.get("/timeline", response_model=AlertTimeline)
def alerts_timeline(
    db: Session = Depends(get_db),
    station_key: int = Query(4),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
) -> AlertTimeline:
    meta = alerts_meta(db)
    end = min(date_to or meta.default_to, meta.data_max)
    start = max(date_from or (end - timedelta(days=6)), meta.data_min)
    if start > end:
        start = end
    rows = fetch_all(
        db,
        """
        SELECT target_time, actual_pm25, predicted_proba, actual_alert,
               predicted_alert, persistence_alert, outcome,
               probability_cutoff, alert_threshold
        FROM mart.mart_pm25_alerts
        WHERE station_key = :station_key
          AND split = 'test'
          AND target_time::date BETWEEN :start AND :end
        ORDER BY target_time
        """,
        {"station_key": station_key, "start": start, "end": end},
    )
    return AlertTimeline(
        station_key=station_key,
        date_from=start,
        date_to=end,
        probability_cutoff=as_float(rows[0]["probability_cutoff"]) if rows else None,
        alert_threshold=as_float(rows[0]["alert_threshold"]) if rows else None,
        series=[
            AlertPoint(
                target_time=r["target_time"],
                actual_pm25=as_float(r["actual_pm25"]),
                predicted_proba=as_float(r["predicted_proba"]),
                actual_alert=int(r["actual_alert"]),
                predicted_alert=int(r["predicted_alert"]),
                persistence_alert=int(r["persistence_alert"]),
                outcome=r["outcome"],
            )
            for r in rows
        ],
    )
