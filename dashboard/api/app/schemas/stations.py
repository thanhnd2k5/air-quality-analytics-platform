from pydantic import BaseModel, ConfigDict


class StationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    station_key: int
    station_code: str | None = None
    station_name: str
    district: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    coordinate_status: str | None = None
    cluster_id: int | None = None
    cluster_label: str | None = None
