from datetime import date

from pydantic import BaseModel


class ClusterStation(BaseModel):
    station_key: int
    station_name: str
    district: str | None = None


class ClusterGroup(BaseModel):
    cluster_id: int
    cluster_label: str
    label_vi: str
    n_stations: int
    pm25_avg: float | None = None
    no2_avg: float | None = None
    co_avg: float | None = None
    stations: list[ClusterStation]


class KSelectionPoint(BaseModel):
    method: str
    k: int
    silhouette: float
    inertia: float | None = None


class ClustersResponse(BaseModel):
    method: str
    k: int
    silhouette: float
    window_from: date
    window_to: date
    k_grid: list[KSelectionPoint]
    groups: list[ClusterGroup]
