from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.coerce import as_float
from app.db import fetch_all, fetch_one, get_db
from app.errors import EmptyMartError
from app.schemas.predictions import (
    PredictionMetrics,
    PredictionPoint,
    PredictionsResponse,
)

router = APIRouter(prefix="/predictions", tags=["predictions"])

SplitFilter = Literal["train", "val", "test"]


def _prediction_bounds(db: Session) -> tuple[date, date]:
    row = fetch_one(
        db,
        """
        SELECT
            MIN(target_time)::date AS min_day,
            MAX(target_time)::date AS max_day
        FROM mart.mart_pm25_predictions
        """,
    )
    if not row or row["min_day"] is None:
        raise EmptyMartError("mart.mart_pm25_predictions is empty")
    return row["min_day"], row["max_day"]


def _resolve_pred_range(
    db: Session,
    date_from: date | None,
    date_to: date | None,
    *,
    default_days: int = 14,
) -> tuple[date, date]:
    min_day, max_day = _prediction_bounds(db)
    end = date_to or max_day
    start = date_from or (end - timedelta(days=default_days - 1))
    if start < min_day:
        start = min_day
    if end > max_day:
        end = max_day
    if start > end:
        start = end
    return start, end


@router.get("/meta")
def predictions_meta(db: Session = Depends(get_db)) -> dict:
    min_day, max_day = _prediction_bounds(db)
    default_from, default_to = _resolve_pred_range(db, None, None)
    versions = fetch_all(
        db,
        """
        SELECT DISTINCT model_version
        FROM mart.mart_pm25_predictions
        ORDER BY model_version
        """,
    )
    return {
        "data_min": min_day,
        "data_max": max_day,
        "default_from": default_from,
        "default_to": default_to,
        "model_versions": [r["model_version"] for r in versions],
    }


@router.get("", response_model=PredictionsResponse)
def list_predictions(
    db: Session = Depends(get_db),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    station_key: int | None = Query(None),
    split: SplitFilter | None = Query(None),
    limit: int = Query(500, ge=1, le=2000),
) -> PredictionsResponse:
    start, end = _resolve_pred_range(db, date_from, date_to)
    params: dict = {"start": start, "end": end, "limit": limit}
    filters = [
        "p.target_time::date >= :start",
        "p.target_time::date <= :end",
    ]
    if station_key is not None:
        filters.append("p.station_key = :station_key")
        params["station_key"] = station_key
    if split is not None:
        filters.append("p.split = :split")
        params["split"] = split
    where = " AND ".join(filters)

    metrics_rows = fetch_all(
        db,
        f"""
        SELECT
            p.split,
            COUNT(*)::int AS n,
            AVG(ABS(p.actual_pm25 - p.predicted_pm25)) AS mae_model,
            AVG(ABS(p.actual_pm25 - p.predicted_pm25_persistence)) AS mae_persistence
        FROM mart.mart_pm25_predictions AS p
        WHERE {where}
          AND p.actual_pm25 IS NOT NULL
        GROUP BY p.split
        ORDER BY CASE p.split
            WHEN 'train' THEN 1
            WHEN 'val' THEN 2
            WHEN 'test' THEN 3
            ELSE 4
        END
        """,
        params,
    )

    version_row = fetch_one(
        db,
        f"""
        SELECT p.model_version
        FROM mart.mart_pm25_predictions AS p
        WHERE {where}
        LIMIT 1
        """,
        params,
    )

    # Single station: raw series. All stations: hourly city mean; split label = "aggregate".
    if station_key is not None:
        series_sql = f"""
        SELECT
            p.target_time,
            p.actual_pm25,
            p.predicted_pm25,
            p.predicted_pm25_persistence,
            p.absolute_error,
            p.split
        FROM mart.mart_pm25_predictions AS p
        WHERE {where}
        ORDER BY p.target_time
        LIMIT :limit
        """
    else:
        series_sql = f"""
        SELECT
            date_trunc('hour', p.target_time) AS target_time,
            AVG(p.actual_pm25) AS actual_pm25,
            AVG(p.predicted_pm25) AS predicted_pm25,
            AVG(p.predicted_pm25_persistence) AS predicted_pm25_persistence,
            AVG(p.absolute_error) AS absolute_error,
            'aggregate'::text AS split
        FROM mart.mart_pm25_predictions AS p
        WHERE {where}
        GROUP BY date_trunc('hour', p.target_time)
        ORDER BY 1
        LIMIT :limit
        """

    series_rows = fetch_all(db, series_sql, params)

    return PredictionsResponse(
        date_from=start,
        date_to=end,
        station_key=station_key,
        split=split,
        model_version=version_row["model_version"] if version_row else None,
        metrics=[
            PredictionMetrics(
                split=r["split"],
                n=r["n"],
                mae_model=as_float(r["mae_model"]),
                mae_persistence=as_float(r["mae_persistence"]),
            )
            for r in metrics_rows
        ],
        series=[
            PredictionPoint(
                target_time=r["target_time"],
                actual_pm25=as_float(r["actual_pm25"]),
                predicted_pm25=as_float(r["predicted_pm25"]),
                predicted_pm25_persistence=as_float(
                    r["predicted_pm25_persistence"]
                ),
                absolute_error=as_float(r["absolute_error"]),
                split=r["split"],
            )
            for r in series_rows
        ],
    )
