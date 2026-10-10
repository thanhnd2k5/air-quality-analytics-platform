from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.coerce import as_float
from app.dates import resolve_date_range
from app.db import fetch_all, get_db
from app.schemas.episodes import (
    EpisodeRow,
    EpisodeSummaryRow,
    EpisodesResponse,
    MultiStationEventRow,
)

router = APIRouter(prefix="/episodes", tags=["episodes"])


@router.get("", response_model=EpisodesResponse)
def list_episodes(
    db: Session = Depends(get_db),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    station_key: int | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
) -> EpisodesResponse:
    start, end = resolve_date_range(db, date_from, date_to)
    params: dict = {"start": start, "end": end, "limit": limit}
    station_filter = ""
    if station_key is not None:
        station_filter = "AND e.station_key = :station_key"
        params["station_key"] = station_key

    summary_rows = fetch_all(
        db,
        f"""
        SELECT
            e.station_key,
            e.station_name,
            COUNT(*)::int AS episode_count,
            AVG(e.duration_hours) AS duration_hours_avg,
            SUM(e.duration_hours)::int AS duration_hours_sum,
            AVG(e.pm25_mean) AS pm25_mean_avg,
            MAX(e.pm25_max) AS pm25_max_max
        FROM mart.mart_pm25_episodes AS e
        WHERE e.start_time::date <= :end
          AND e.end_time::date >= :start
          {station_filter}
        GROUP BY e.station_key, e.station_name
        ORDER BY episode_count DESC, e.station_name
        """,
        params,
    )

    episode_rows = fetch_all(
        db,
        f"""
        SELECT
            e.episode_id,
            e.station_key,
            e.station_name,
            e.start_time,
            e.end_time,
            e.duration_hours,
            e.pm25_mean,
            e.pm25_max,
            e.year,
            e.season,
            e.temperature_c_avg,
            e.relative_humidity_pct_avg,
            e.wind_speed_m_s_avg,
            e.rain_mm_sum,
            e.cloud_cover_pct_avg,
            e.threshold_ug_m3,
            e.min_hours
        FROM mart.mart_pm25_episodes AS e
        WHERE e.start_time::date <= :end
          AND e.end_time::date >= :start
          {station_filter}
        ORDER BY e.start_time DESC
        LIMIT :limit
        """,
        params,
    )

    multi_rows = fetch_all(
        db,
        """
        SELECT
            m.event_id,
            m.start_time,
            m.end_time,
            m.duration_hours,
            m.peak_station_count,
            m.mean_station_count,
            m.multi_station_k
        FROM mart.mart_pm25_multi_station_events AS m
        WHERE m.start_time::date <= :end
          AND m.end_time::date >= :start
        ORDER BY m.start_time DESC
        LIMIT :limit
        """,
        {"start": start, "end": end, "limit": limit},
    )

    return EpisodesResponse(
        date_from=start,
        date_to=end,
        station_key=station_key,
        summary=[
            EpisodeSummaryRow(
                station_key=r["station_key"],
                station_name=r["station_name"],
                episode_count=r["episode_count"],
                duration_hours_avg=as_float(r["duration_hours_avg"]),
                duration_hours_sum=r["duration_hours_sum"],
                pm25_mean_avg=as_float(r["pm25_mean_avg"]),
                pm25_max_max=as_float(r["pm25_max_max"]),
            )
            for r in summary_rows
        ],
        episodes=[
            EpisodeRow(
                episode_id=r["episode_id"],
                station_key=r["station_key"],
                station_name=r["station_name"],
                start_time=r["start_time"],
                end_time=r["end_time"],
                duration_hours=r["duration_hours"],
                pm25_mean=as_float(r["pm25_mean"]),
                pm25_max=as_float(r["pm25_max"]),
                year=r["year"],
                season=r["season"],
                temperature_c_avg=as_float(r["temperature_c_avg"]),
                relative_humidity_pct_avg=as_float(r["relative_humidity_pct_avg"]),
                wind_speed_m_s_avg=as_float(r["wind_speed_m_s_avg"]),
                rain_mm_sum=as_float(r["rain_mm_sum"]),
                cloud_cover_pct_avg=as_float(r["cloud_cover_pct_avg"]),
                threshold_ug_m3=as_float(r["threshold_ug_m3"]),
                min_hours=r["min_hours"],
            )
            for r in episode_rows
        ],
        multi_station_events=[
            MultiStationEventRow(
                event_id=r["event_id"],
                start_time=r["start_time"],
                end_time=r["end_time"],
                duration_hours=r["duration_hours"],
                peak_station_count=r["peak_station_count"],
                mean_station_count=as_float(r["mean_station_count"]),
                multi_station_k=r["multi_station_k"],
            )
            for r in multi_rows
        ],
    )
