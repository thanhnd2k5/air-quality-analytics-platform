from datetime import date

from pydantic import BaseModel


class WeatherSeriesPoint(BaseModel):
    date_day: date
    pm25_ug_m3_avg: float | None
    temperature_c_avg: float | None
    relative_humidity_pct_avg: float | None
    wind_speed_m_s_avg: float | None
    rain_mm_sum: float | None
    cloud_cover_pct_avg: float | None
    pressure_hpa_avg: float | None
    dew_point_c_avg: float | None


class WeatherScatterPoint(BaseModel):
    date_day: date
    pm25_ug_m3_avg: float | None
    weather_value: float | None


class WeatherResponse(BaseModel):
    date_from: date
    date_to: date
    station_key: int | None = None
    series: list[WeatherSeriesPoint]
    scatter_variable: str
    scatter: list[WeatherScatterPoint]
