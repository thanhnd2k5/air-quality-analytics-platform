from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dates import resolve_date_range
from app.db import fetch_all, get_db
from app.schemas.compare import StationCompareResponse, StationCompareRow

router = APIRouter(prefix="/stations", tags=["stations"])


@router.get("/compare", response_model=StationCompareResponse)
def compare_stations(
    db: Session = Depends(get_db),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
) -> StationCompareResponse:
    start, end = resolve_date_range(db, date_from, date_to)
    rows = fetch_all(
        db,
        """
        WITH agg AS (
            SELECT
                d.station_key,
                d.station_name,
                d.district,
                AVG(d.pm25_ug_m3_avg) AS pm25_avg,
                AVG(d.pm10_ug_m3_avg) AS pm10_avg,
                AVG(d.o3_ug_m3_avg) AS o3_avg,
                COUNT(*)::int AS day_count
            FROM mart.mart_station_daily AS d
            WHERE d.date_day >= :start
              AND d.date_day <= :end
            GROUP BY d.station_key, d.station_name, d.district
        )
        SELECT
            a.station_key,
            a.station_name,
            a.district,
            c.cluster_id,
            c.cluster_label,
            a.pm25_avg,
            a.pm10_avg,
            a.o3_avg,
            a.day_count,
            RANK() OVER (ORDER BY a.pm25_avg DESC NULLS LAST)::int AS rank_pm25
        FROM agg AS a
        LEFT JOIN mart.mart_station_cluster AS c
            ON a.station_key = c.station_key
        ORDER BY rank_pm25, a.station_name
        """,
        {"start": start, "end": end},
    )
    return StationCompareResponse(
        date_from=start,
        date_to=end,
        rows=[
            StationCompareRow(
                station_key=r["station_key"],
                station_name=r["station_name"],
                district=r["district"],
                cluster_id=r["cluster_id"],
                cluster_label=r["cluster_label"],
                pm25_avg=float(r["pm25_avg"]) if r["pm25_avg"] is not None else None,
                pm10_avg=float(r["pm10_avg"]) if r["pm10_avg"] is not None else None,
                o3_avg=float(r["o3_avg"]) if r["o3_avg"] is not None else None,
                day_count=r["day_count"],
                rank_pm25=r["rank_pm25"],
            )
            for r in rows
        ],
    )
