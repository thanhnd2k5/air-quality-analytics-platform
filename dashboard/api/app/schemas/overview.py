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
    so2_avg: float | None
    no2_avg: float | None
    co_avg: float | None
    station_day_rows: int
    pm25_day_rows: int
    days_pm25_ge_115: int
    episode_count: int
    duration_hours_avg: float | None
    duration_hours_max: int | None
    multi_station_event_count: int | None = None


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
