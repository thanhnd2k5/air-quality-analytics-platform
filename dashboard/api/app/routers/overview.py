from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dates import data_date_bounds, resolve_date_range
from app.db import fetch_all, fetch_one, get_db
from app.schemas.overview import OverviewKpis, OverviewTrends, TrendPoint

router = APIRouter(prefix="/overview", tags=["overview"])


@router.get("/meta")
def overview_meta(db: Session = Depends(get_db)) -> dict:
    min_day, max_day = data_date_bounds(db)
    default_from, default_to = resolve_date_range(db, None, None)
    return {
        "data_min": min_day,
        "data_max": max_day,
        "default_from": default_from,
        "default_to": default_to,
    }


@router.get("/kpis", response_model=OverviewKpis)
def overview_kpis(
    db: Session = Depends(get_db),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    station_key: int | None = Query(None),
) -> OverviewKpis:
    start, end = resolve_date_range(db, date_from, date_to)
    params: dict = {"start": start, "end": end}
    station_filter = ""
    if station_key is not None:
        station_filter = "AND d.station_key = :station_key"
        params["station_key"] = station_key

    agg = fetch_one(
        db,
        f"""
        SELECT
            AVG(d.pm25_ug_m3_avg) AS pm25_avg,
            AVG(d.pm10_ug_m3_avg) AS pm10_avg,
            AVG(d.o3_ug_m3_avg) AS o3_avg,
            COUNT(*)::int AS station_day_rows,
            COUNT(d.pm25_ug_m3_avg)::int AS pm25_day_rows
        FROM mart.mart_station_daily AS d
        WHERE d.date_day >= :start
          AND d.date_day <= :end
          {station_filter}
        """,
        params,
    )
    assert agg is not None

    ep_params = {"start": start, "end": end}
    ep_filter = ""
    if station_key is not None:
        ep_filter = "AND e.station_key = :station_key"
        ep_params["station_key"] = station_key
    ep = fetch_one(
        db,
        f"""
        SELECT COUNT(*)::int AS episode_count
        FROM mart.mart_pm25_episodes AS e
        WHERE e.start_time::date <= :end
          AND e.end_time::date >= :start
          {ep_filter}
        """,
        ep_params,
    )

    return OverviewKpis(
        date_from=start,
        date_to=end,
        station_key=station_key,
        pm25_avg=float(agg["pm25_avg"]) if agg["pm25_avg"] is not None else None,
        pm10_avg=float(agg["pm10_avg"]) if agg["pm10_avg"] is not None else None,
        o3_avg=float(agg["o3_avg"]) if agg["o3_avg"] is not None else None,
        station_day_rows=agg["station_day_rows"],
        pm25_day_rows=agg["pm25_day_rows"],
        episode_count=ep["episode_count"] if ep else 0,
    )


@router.get("/trends", response_model=OverviewTrends)
def overview_trends(
    db: Session = Depends(get_db),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    station_key: int | None = Query(None),
) -> OverviewTrends:
    start, end = resolve_date_range(db, date_from, date_to)
    params: dict = {"start": start, "end": end}
    if station_key is not None:
        params["station_key"] = station_key
        sql = """
        SELECT
            d.date_day::date AS date_day,
            d.pm25_ug_m3_avg,
            d.pm10_ug_m3_avg,
            d.o3_ug_m3_avg
        FROM mart.mart_station_daily AS d
        WHERE d.date_day >= :start
          AND d.date_day <= :end
          AND d.station_key = :station_key
        ORDER BY d.date_day
        """
    else:
        sql = """
        SELECT
            d.date_day::date AS date_day,
            AVG(d.pm25_ug_m3_avg) AS pm25_ug_m3_avg,
            AVG(d.pm10_ug_m3_avg) AS pm10_ug_m3_avg,
            AVG(d.o3_ug_m3_avg) AS o3_ug_m3_avg
        FROM mart.mart_station_daily AS d
        WHERE d.date_day >= :start
          AND d.date_day <= :end
        GROUP BY d.date_day
        ORDER BY d.date_day
        """

    rows = fetch_all(db, sql, params)
    points = [
        TrendPoint(
            date_day=r["date_day"],
            pm25_ug_m3_avg=(
                float(r["pm25_ug_m3_avg"]) if r["pm25_ug_m3_avg"] is not None else None
            ),
            pm10_ug_m3_avg=(
                float(r["pm10_ug_m3_avg"]) if r["pm10_ug_m3_avg"] is not None else None
            ),
            o3_ug_m3_avg=(
                float(r["o3_ug_m3_avg"]) if r["o3_ug_m3_avg"] is not None else None
            ),
        )
        for r in rows
    ]
    return OverviewTrends(
        date_from=start,
        date_to=end,
        station_key=station_key,
        points=points,
    )
