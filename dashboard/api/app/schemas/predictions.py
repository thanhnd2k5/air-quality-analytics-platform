from datetime import date, datetime

from pydantic import BaseModel


class PredictionMetrics(BaseModel):
    split: str
    n: int
    mae_model: float | None
    mae_persistence: float | None


class PredictionPoint(BaseModel):
    target_time: datetime
    actual_pm25: float | None
    predicted_pm25: float | None
    predicted_pm25_persistence: float | None
    absolute_error: float | None
    split: str


class PredictionsResponse(BaseModel):
    date_from: date
    date_to: date
    station_key: int | None = None
    split: str | None = None
    model_version: str | None = None
    metrics: list[PredictionMetrics]
    series: list[PredictionPoint]
