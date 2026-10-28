from datetime import date

from pydantic import BaseModel


class StationCompareRow(BaseModel):
    station_key: int
    station_name: str
    district: str | None = None
    cluster_id: int | None = None
    cluster_label: str | None = None
    pm25_avg: float | None
    pm10_avg: float | None
    o3_avg: float | None
    day_count: int
    episode_count: int
    rank_pm25: int


class StationCompareResponse(BaseModel):
    date_from: date
    date_to: date
    rows: list[StationCompareRow]
