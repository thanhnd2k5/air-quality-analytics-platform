"""Station reference helpers (seed CSV)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

DEFAULT_STATIONS_CSV = Path("data/raw/reference/stations.csv")


@dataclass(frozen=True)
class StationRef:
    station_id: int
    station_code: str
    station_name: str
    latitude: float
    longitude: float
    district: str
    coordinate_status: str
    metadata_source: str


def load_stations(path: Path | None = None) -> dict[str, StationRef]:
    csv_path = path or DEFAULT_STATIONS_CSV
    df = pd.read_csv(csv_path)
    required = {
        "station_id",
        "station_code",
        "station_name",
        "latitude",
        "longitude",
        "district",
        "coordinate_status",
        "metadata_source",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"stations.csv missing columns: {sorted(missing)}")

    out: dict[str, StationRef] = {}
    for row in df.itertuples(index=False):
        ref = StationRef(
            station_id=int(row.station_id),
            station_code=str(row.station_code),
            station_name=str(row.station_name),
            latitude=float(row.latitude),
            longitude=float(row.longitude),
            district=str(row.district),
            coordinate_status=str(row.coordinate_status),
            metadata_source=str(row.metadata_source),
        )
        out[ref.station_name] = ref
    return out


def get_station(station: str, path: Path | None = None) -> StationRef:
    stations = load_stations(path)
    if station not in stations:
        raise KeyError(f"Unknown station '{station}'. Known: {sorted(stations)}")
    return stations[station]


def list_station_names(path: Path | None = None) -> list[str]:
    return sorted(load_stations(path).keys())
