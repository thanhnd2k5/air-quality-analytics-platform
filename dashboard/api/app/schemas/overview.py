from datetime import date

from pydantic import BaseModel


class DateRangeMeta(BaseModel):
    date_from: date
    date_to: date
    data_min: date
    data_max: date


class OverviewKpis(BaseModel):
    date_from: date
    date_to: date
    station_key: int | None = None
    pm25_avg: float | None
    pm10_avg: float | None
    o3_avg: float | None
    station_day_rows: int
    pm25_day_rows: int
    episode_count: int


class TrendPoint(BaseModel):
    date_day: date
    pm25_ug_m3_avg: float | None
    pm10_ug_m3_avg: float | None
    o3_ug_m3_avg: float | None


class OverviewTrends(BaseModel):
    date_from: date
    date_to: date
    station_key: int | None = None
    points: list[TrendPoint]
