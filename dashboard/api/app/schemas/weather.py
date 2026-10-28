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


class WindRosePoint(BaseModel):
    direction: str
    azimuth_deg: float
    hours: int
    exceed_pct: float | None
    pm25_avg: float | None


class WeatherResponse(BaseModel):
    date_from: date
    date_to: date
    station_key: int | None = None
    series: list[WeatherSeriesPoint]
    scatter_variable: str
    scatter: list[WeatherScatterPoint]


class WindRoseResponse(BaseModel):
    """Hourly PM2.5 per 16-point wind direction over the chosen days / station."""

    date_from: date
    date_to: date
    station_key: int | None = None
    points: list[WindRosePoint]
