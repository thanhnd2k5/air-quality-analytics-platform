from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import fetch_all, get_db
from app.schemas.stations import StationOut

router = APIRouter(prefix="/stations", tags=["stations"])

STATIONS_SQL = """
SELECT
    s.station_key,
    s.station_code,
    s.station_name,
    s.district,
    s.latitude,
    s.longitude,
    s.coordinate_status,
    c.cluster_id,
    c.cluster_label
FROM dwh.dim_station AS s
LEFT JOIN mart.mart_station_cluster AS c
    ON s.station_key = c.station_key
ORDER BY s.station_name
"""


@router.get("", response_model=list[StationOut])
def list_stations(db: Session = Depends(get_db)) -> list[StationOut]:
    rows = fetch_all(db, STATIONS_SQL)
    return [StationOut.model_validate(row) for row in rows]
