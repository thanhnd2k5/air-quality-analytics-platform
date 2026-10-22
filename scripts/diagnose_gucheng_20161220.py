"""Hourly diagnosis of Gucheng on 2016-12-20. Does not train or touch the lock.

Writes a table of own PM2.5, the three nearest stations, wind, and M0/M2 error.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from src.eda.db import read_sql  # noqa: E402
from src.forecasting.constants import TARGET_COL  # noqa: E402
from src.forecasting.spatial_calendar import haversine_km, nearest_neighbor_table  # noqa: E402

PRED = ROOT / "artifacts" / "forecasting" / "spatial_calendar_ablation" / "predictions_m0_m3.parquet"
STATIONS = ROOT / "data" / "raw" / "reference" / "stations.csv"
OUT = ROOT / "artifacts" / "forecasting" / "upwind_poc"


def _bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import numpy as np

    p1, p2 = np.radians(lat1), np.radians(lat2)
    dl = np.radians(lon2 - lon1)
    x = np.sin(dl) * np.cos(p2)
    y = np.cos(p1) * np.sin(p2) - np.sin(p1) * np.cos(p2) * np.cos(dl)
    return float((np.degrees(np.arctan2(x, y)) + 360.0) % 360.0)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    weather = read_sql(
        """
        select s.station_name,
               f.event_time_local,
               f.pm25_ug_m3,
               f.wind_speed_m_s,
               w.wind_direction,
               w.azimuth_deg
        from dwh.fact_air_quality_hourly f
        join dwh.dim_station s on f.station_key = s.station_key
        join dwh.dim_wind_direction w on f.wind_direction_key = w.wind_direction_key
        where f.event_time_local >= '2016-12-20 00:00:00'
          and f.event_time_local < '2016-12-21 02:00:00'
        """
    )
    weather["event_time_local"] = pd.to_datetime(weather["event_time_local"])

    stations = pd.read_csv(STATIONS)
    neighbors = nearest_neighbor_table(stations)
    gucheng_neighbors = neighbors[neighbors["station_name"] == "Gucheng"].sort_values("neighbor_rank")
    origin = stations[stations["station_name"] == "Gucheng"].iloc[0]
    bearings = []
    for row in gucheng_neighbors.itertuples(index=False):
        other = stations[stations["station_name"] == row.neighbor_name].iloc[0]
        bearings.append(
            {
                "neighbor_name": row.neighbor_name,
                "distance_km": row.distance_km,
                "weight": row.weight,
                "bearing_from_gucheng_deg": _bearing_deg(
                    float(origin.latitude),
                    float(origin.longitude),
                    float(other.latitude),
                    float(other.longitude),
                ),
            }
        )
    pd.DataFrame(bearings).to_csv(OUT / "gucheng_neighbor_bearings.csv", index=False)

    preds = pd.read_parquet(PRED)
    preds["event_time_local"] = pd.to_datetime(preds["event_time_local"])
    preds["target_time_local"] = pd.to_datetime(preds["target_time_local"])
    g = preds[
        preds["station_name"].eq("Gucheng")
        & preds["target_time_local"].between("2016-12-20 00:00:00", "2016-12-21 00:00:00")
    ].copy()

    own = weather[weather["station_name"].eq("Gucheng")][
        ["event_time_local", "pm25_ug_m3", "wind_speed_m_s", "wind_direction", "azimuth_deg"]
    ]
    table = g.merge(own, on="event_time_local", how="left", suffixes=("", "_wx"))
    # pm25_ug_m3 from predictions is the origin value; weather pm25 is the same hour.
    table = table.rename(columns={"pm25_ug_m3_wx": "pm25_warehouse"})
    for neighbor in gucheng_neighbors["neighbor_name"]:
        sub = weather[weather["station_name"].eq(neighbor)][
            ["event_time_local", "pm25_ug_m3"]
        ].rename(columns={"pm25_ug_m3": f"pm25_{neighbor}"})
        table = table.merge(sub, on="event_time_local", how="left")

    table["actual_delta"] = table[TARGET_COL] - table["pm25_ug_m3"]
    neighbor_cols = [f"pm25_{n}" for n in gucheng_neighbors["neighbor_name"]]
    table["nearest3_mean"] = table[neighbor_cols].mean(axis=1)
    table["nearest3_minus_gucheng"] = table["nearest3_mean"] - table["pm25_ug_m3"]
    keep = [
        "event_time_local",
        "target_time_local",
        "pm25_ug_m3",
        TARGET_COL,
        "actual_delta",
        *neighbor_cols,
        "nearest3_mean",
        "nearest3_minus_gucheng",
        "wind_direction",
        "azimuth_deg",
        "wind_speed_m_s",
        "y_hat_m0",
        "y_hat_m2",
        "signed_m0",
        "signed_m2",
    ]
    out = table[keep].sort_values("target_time_local")
    path = OUT / "gucheng_20161220_hourly.csv"
    out.to_csv(path, index=False)
    afternoon = out[out["target_time_local"].between("2016-12-20 08:00:00", "2016-12-20 21:00:00")]
    print(afternoon.to_string(index=False))
    print("wrote", path)


if __name__ == "__main__":
    main()
