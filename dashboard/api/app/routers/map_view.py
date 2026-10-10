from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.coerce import as_float
from app.dates import data_date_bounds
from app.db import fetch_all, fetch_one, get_db
from app.schemas.map import MapSnapshotResponse, MapStationPoint

router = APIRouter(prefix="/map", tags=["map"])

COORD_NOTE = (
    "Tọa độ LITERATURE (Foreback et al. 2022 ACP Supp. Table S1) — "
    "12 marker, không phải bản đồ phủ nội suy."
)


@router.get("/snapshot", response_model=MapSnapshotResponse)
def map_snapshot(
    db: Session = Depends(get_db),
    date_day: date | None = Query(
        None, description="Ngày PM daily; mặc định = ngày cuối có data"
    ),
) -> MapSnapshotResponse:
    data_min, data_max = data_date_bounds(db)
    day = date_day or data_max
    if day < data_min:
        day = data_min
    if day > data_max:
        day = data_max

    nearest = fetch_one(
        db,
        """
        SELECT MAX(date_day)::date AS day
        FROM mart.mart_station_daily
        WHERE date_day <= :day
        """,
        {"day": day},
    )
    use_day = nearest["day"] if nearest and nearest["day"] else day

    rows = fetch_all(
        db,
        """
        SELECT
            s.station_key,
            s.station_name,
            s.district,
            s.latitude,
            s.longitude,
            s.coordinate_status,
            c.cluster_id,
            c.cluster_label,
            d.pm25_ug_m3_avg,
            d.date_day::date AS date_day
        FROM dwh.dim_station AS s
        LEFT JOIN mart.mart_station_cluster AS c
            ON s.station_key = c.station_key
        LEFT JOIN mart.mart_station_daily AS d
            ON s.station_key = d.station_key
           AND d.date_day = :day
        WHERE s.latitude IS NOT NULL
          AND s.longitude IS NOT NULL
        ORDER BY s.station_name
        """,
        {"day": use_day},
    )

    return MapSnapshotResponse(
        date_day=use_day,
        data_min=data_min,
        data_max=data_max,
        coordinate_note=COORD_NOTE,
        points=[
            MapStationPoint(
                station_key=r["station_key"],
                station_name=r["station_name"],
                district=r["district"],
                latitude=float(r["latitude"]),
                longitude=float(r["longitude"]),
                coordinate_status=r["coordinate_status"],
                cluster_id=r["cluster_id"],
                cluster_label=r["cluster_label"],
                pm25_ug_m3_avg=as_float(r["pm25_ug_m3_avg"]),
                date_day=r["date_day"],
            )
            for r in rows
        ],
    )
