from datetime import date, datetime

from pydantic import BaseModel


class EpisodeSummaryRow(BaseModel):
    station_key: int
    station_name: str
    episode_count: int
    duration_hours_avg: float | None
    duration_hours_sum: int
    pm25_mean_avg: float | None
    pm25_max_max: float | None


class EpisodeRow(BaseModel):
    episode_id: int
    station_key: int
    station_name: str
    start_time: datetime
    end_time: datetime
    duration_hours: int
    pm25_mean: float | None
    pm25_max: float | None
    year: int | None = None
    season: str | None = None
    temperature_c_avg: float | None = None
    relative_humidity_pct_avg: float | None = None
    wind_speed_m_s_avg: float | None = None
    rain_mm_sum: float | None = None
    cloud_cover_pct_avg: float | None = None
    threshold_ug_m3: float | None = None
    min_hours: int | None = None


class MultiStationEventRow(BaseModel):
    event_id: int
    start_time: datetime
    end_time: datetime
    duration_hours: int
    peak_station_count: int
    mean_station_count: float | None
    multi_station_k: int


class EpisodesResponse(BaseModel):
    date_from: date
    date_to: date
    station_key: int | None = None
    summary: list[EpisodeSummaryRow]
    episodes: list[EpisodeRow]
    multi_station_events: list[MultiStationEventRow]
