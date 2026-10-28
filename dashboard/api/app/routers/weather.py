from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.coerce import as_float
from app.dates import resolve_date_range
from app.db import fetch_all, get_db
from app.schemas.weather import (
    WeatherResponse,
    WeatherScatterPoint,
    WeatherSeriesPoint,
    WindRosePoint,
    WindRoseResponse,
)

router = APIRouter(prefix="/weather", tags=["weather"])

ScatterVar = Literal[
    "temperature_c_avg",
    "relative_humidity_pct_avg",
    "wind_speed_m_s_avg",
    "rain_mm_sum",
    "cloud_cover_pct_avg",
    "pressure_hpa_avg",
    "dew_point_c_avg",
]

SCATTER_COLUMNS = {
    "temperature_c_avg": "w.temperature_c_avg",
    "relative_humidity_pct_avg": "w.relative_humidity_pct_avg",
    "wind_speed_m_s_avg": "w.wind_speed_m_s_avg",
    "rain_mm_sum": "w.rain_mm_sum",
    "cloud_cover_pct_avg": "w.cloud_cover_pct_avg",
    "pressure_hpa_avg": "w.pressure_hpa_avg",
    "dew_point_c_avg": "w.dew_point_c_avg",
}


@router.get("", response_model=WeatherResponse)
def weather_analysis(
    db: Session = Depends(get_db),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    station_key: int | None = Query(None),
    scatter_variable: ScatterVar = Query("temperature_c_avg"),
) -> WeatherResponse:
    if scatter_variable not in SCATTER_COLUMNS:
        raise HTTPException(status_code=400, detail="Invalid scatter_variable")

    start, end = resolve_date_range(db, date_from, date_to)
    params: dict = {"start": start, "end": end}
    station_filter = ""
    if station_key is not None:
        station_filter = "AND w.station_key = :station_key"
        params["station_key"] = station_key

    if station_key is not None:
        series_sql = f"""
        SELECT
            w.date_day::date AS date_day,
            w.pm25_ug_m3_avg,
            w.temperature_c_avg,
            w.relative_humidity_pct_avg,
            w.wind_speed_m_s_avg,
            w.rain_mm_sum,
            w.cloud_cover_pct_avg,
            w.pressure_hpa_avg,
            w.dew_point_c_avg
        FROM mart.mart_pollution_weather AS w
        WHERE w.date_day >= :start
          AND w.date_day <= :end
          {station_filter}
        ORDER BY w.date_day
        """
    else:
        series_sql = """
        SELECT
            w.date_day::date AS date_day,
            AVG(w.pm25_ug_m3_avg) AS pm25_ug_m3_avg,
            AVG(w.temperature_c_avg) AS temperature_c_avg,
            AVG(w.relative_humidity_pct_avg) AS relative_humidity_pct_avg,
            AVG(w.wind_speed_m_s_avg) AS wind_speed_m_s_avg,
            AVG(w.rain_mm_sum) AS rain_mm_sum,
            AVG(w.cloud_cover_pct_avg) AS cloud_cover_pct_avg,
            AVG(w.pressure_hpa_avg) AS pressure_hpa_avg,
            AVG(w.dew_point_c_avg) AS dew_point_c_avg
        FROM mart.mart_pollution_weather AS w
        WHERE w.date_day >= :start
          AND w.date_day <= :end
        GROUP BY w.date_day
        ORDER BY w.date_day
        """

    series_rows = fetch_all(db, series_sql, params)
    weather_col = SCATTER_COLUMNS[scatter_variable]

    if station_key is not None:
        scatter_sql = f"""
        SELECT
            w.date_day::date AS date_day,
            w.pm25_ug_m3_avg,
            {weather_col} AS weather_value
        FROM mart.mart_pollution_weather AS w
        WHERE w.date_day >= :start
          AND w.date_day <= :end
          {station_filter}
          AND w.pm25_ug_m3_avg IS NOT NULL
          AND {weather_col} IS NOT NULL
        ORDER BY w.date_day
        """
    else:
        scatter_sql = f"""
        SELECT
            w.date_day::date AS date_day,
            AVG(w.pm25_ug_m3_avg) AS pm25_ug_m3_avg,
            AVG({weather_col}) AS weather_value
        FROM mart.mart_pollution_weather AS w
        WHERE w.date_day >= :start
          AND w.date_day <= :end
        GROUP BY w.date_day
        HAVING AVG(w.pm25_ug_m3_avg) IS NOT NULL
           AND AVG({weather_col}) IS NOT NULL
        ORDER BY w.date_day
        """

    scatter_rows = fetch_all(db, scatter_sql, params)

    return WeatherResponse(
        date_from=start,
        date_to=end,
        station_key=station_key,
        series=[
            WeatherSeriesPoint(
                date_day=r["date_day"],
                pm25_ug_m3_avg=as_float(r["pm25_ug_m3_avg"]),
                temperature_c_avg=as_float(r["temperature_c_avg"]),
                relative_humidity_pct_avg=as_float(r["relative_humidity_pct_avg"]),
                wind_speed_m_s_avg=as_float(r["wind_speed_m_s_avg"]),
                rain_mm_sum=as_float(r["rain_mm_sum"]),
                cloud_cover_pct_avg=as_float(r["cloud_cover_pct_avg"]),
                pressure_hpa_avg=as_float(r["pressure_hpa_avg"]),
                dew_point_c_avg=as_float(r["dew_point_c_avg"]),
            )
            for r in series_rows
        ],
        scatter_variable=scatter_variable,
        scatter=[
            WeatherScatterPoint(
                date_day=r["date_day"],
                pm25_ug_m3_avg=as_float(r["pm25_ug_m3_avg"]),
                weather_value=as_float(r["weather_value"]),
            )
            for r in scatter_rows
        ],
    )


@router.get("/wind-rose", response_model=WindRoseResponse)
def wind_rose(
    db: Session = Depends(get_db),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    station_key: int | None = Query(None),
) -> WindRoseResponse:
    start, end = resolve_date_range(db, date_from, date_to)
    params: dict = {"start": start, "end": end}
    station_filter = ""
    if station_key is not None:
        station_filter = "AND fact.station_key = :station_key"
        params["station_key"] = station_key

    # Hourly grain from the star schema (the daily mart has no wind direction); calm/unknown dropped.
    sql = f"""
    SELECT
        wind.wind_direction AS direction,
        wind.azimuth_deg,
        COUNT(fact.pm25_ug_m3) AS hours,
        100.0 * AVG((fact.pm25_ug_m3 >= 115)::int) AS exceed_pct,
        AVG(fact.pm25_ug_m3) AS pm25_avg
    FROM dwh.fact_air_quality_hourly AS fact
    JOIN dwh.dim_date AS calendar ON fact.date_key = calendar.date_key
    JOIN dwh.dim_wind_direction AS wind ON fact.wind_direction_key = wind.wind_direction_key
    WHERE calendar.date_day >= :start
      AND calendar.date_day <= :end
      AND wind.azimuth_deg IS NOT NULL
      {station_filter}
    GROUP BY wind.wind_direction, wind.azimuth_deg
    ORDER BY wind.azimuth_deg
    """
    rows = fetch_all(db, sql, params)

    return WindRoseResponse(
        date_from=start,
        date_to=end,
        station_key=station_key,
        points=[
            WindRosePoint(
                direction=r["direction"],
                azimuth_deg=float(r["azimuth_deg"]),
                hours=int(r["hours"]),
                exceed_pct=as_float(r["exceed_pct"]),
                pm25_avg=as_float(r["pm25_avg"]),
            )
            for r in rows
        ],
    )
