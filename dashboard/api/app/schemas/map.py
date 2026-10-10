from datetime import date

from pydantic import BaseModel


class MapStationPoint(BaseModel):
    station_key: int
    station_name: str
    district: str | None = None
    latitude: float
    longitude: float
    coordinate_status: str | None = None
    cluster_id: int | None = None
    cluster_label: str | None = None
    pm25_ug_m3_avg: float | None = None
    date_day: date | None = None


class MapSnapshotResponse(BaseModel):
    date_day: date
    data_min: date
    data_max: date
    coordinate_note: str
    points: list[MapStationPoint]
