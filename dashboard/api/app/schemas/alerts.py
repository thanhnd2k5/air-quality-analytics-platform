from datetime import date, datetime

from pydantic import BaseModel


class ConfusionMatrix(BaseModel):
    tp: int
    fp: int
    fn: int
    tn: int
    accuracy: float | None
    precision: float | None
    recall: float | None
    f1: float | None
    onsets: int
    onsets_detected: int


class StationAlertMetrics(BaseModel):
    station_key: int
    station_name: str
    positives: int
    f1_model: float | None
    f1_persistence: float | None
    recall_model: float | None
    recall_persistence: float | None


class AlertSummary(BaseModel):
    split: str
    model_version: str | None
    alert_threshold: float | None
    probability_cutoff: float | None
    n: int
    model: ConfusionMatrix
    persistence: ConfusionMatrix
    stations: list[StationAlertMetrics]


class AlertMeta(BaseModel):
    data_min: date
    data_max: date
    default_from: date
    default_to: date


class AlertPoint(BaseModel):
    target_time: datetime
    actual_pm25: float | None
    predicted_proba: float | None
    actual_alert: int
    predicted_alert: int
    persistence_alert: int
    outcome: str


class AlertTimeline(BaseModel):
    station_key: int
    date_from: date
    date_to: date
    probability_cutoff: float | None
    alert_threshold: float | None
    series: list[AlertPoint]
