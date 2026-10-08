"""Phase 8b EDA query builders — read-only against DWH / marts."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.eda.db import read_sql

POLLUTANTS = (
    ("pm25_ug_m3", "PM2.5"),
    ("pm10_ug_m3", "PM10"),
    ("so2_ug_m3", "SO2"),
    ("no2_ug_m3", "NO2"),
    ("co_ug_m3", "CO"),
    ("o3_ug_m3", "O3"),
)

WEATHER_COLS = (
    ("temperature_c", "temperature"),
    ("relative_humidity_pct", "relative_humidity"),
    ("wind_speed_m_s", "wind_speed"),
    ("pressure_hpa", "pressure"),
    ("rain_mm", "rain"),
    ("cloud_cover_pct", "cloud_cover"),
)


def pm25_by_hour_of_day() -> pd.DataFrame:
    return read_sql(
        """
        select
            fact.time_key as hour_of_day,
            count(fact.pm25_ug_m3) as n,
            round(avg(fact.pm25_ug_m3)::numeric, 2) as pm25_avg,
            round(percentile_cont(0.5) within group (order by fact.pm25_ug_m3)::numeric, 2) as pm25_p50
        from dwh.fact_air_quality_hourly as fact
        where fact.pm25_ug_m3 is not null
        group by fact.time_key
        order by fact.time_key
        """
    )


def pm25_by_month() -> pd.DataFrame:
    return read_sql(
        """
        select
            calendar.year,
            calendar.month,
            calendar.season,
            count(fact.pm25_ug_m3) as n,
            round(avg(fact.pm25_ug_m3)::numeric, 2) as pm25_avg
        from dwh.fact_air_quality_hourly as fact
        inner join dwh.dim_date as calendar on fact.date_key = calendar.date_key
        where fact.pm25_ug_m3 is not null
        group by calendar.year, calendar.month, calendar.season
        order by calendar.year, calendar.month
        """
    )


def pm25_by_season() -> pd.DataFrame:
    return read_sql(
        """
        select
            calendar.season,
            count(*) as hour_count,
            count(fact.pm25_ug_m3) as pm25_hour_count,
            round(avg(fact.pm25_ug_m3)::numeric, 2) as pm25_avg,
            round(percentile_cont(0.5) within group (order by fact.pm25_ug_m3)::numeric, 2) as pm25_p50,
            round(percentile_cont(0.9) within group (order by fact.pm25_ug_m3)::numeric, 2) as pm25_p90,
            round(percentile_cont(0.95) within group (order by fact.pm25_ug_m3)::numeric, 2) as pm25_p95
        from dwh.fact_air_quality_hourly as fact
        inner join dwh.dim_date as calendar on fact.date_key = calendar.date_key
        group by calendar.season
        order by calendar.season
        """
    )


def pm25_by_year() -> pd.DataFrame:
    return read_sql(
        """
        select
            calendar.year,
            count(fact.pm25_ug_m3) as n,
            round(avg(fact.pm25_ug_m3)::numeric, 2) as pm25_avg,
            round(percentile_cont(0.9) within group (order by fact.pm25_ug_m3)::numeric, 2) as pm25_p90
        from dwh.fact_air_quality_hourly as fact
        inner join dwh.dim_date as calendar on fact.date_key = calendar.date_key
        where fact.pm25_ug_m3 is not null
        group by calendar.year
        order by calendar.year
        """
    )


def station_pm25_summary() -> pd.DataFrame:
    return read_sql(
        """
        select
            station.station_name,
            station.district,
            count(fact.pm25_ug_m3) as n,
            round(avg(fact.pm25_ug_m3)::numeric, 2) as pm25_mean,
            round(percentile_cont(0.5) within group (order by fact.pm25_ug_m3)::numeric, 2) as pm25_median,
            round(stddev_samp(fact.pm25_ug_m3)::numeric, 2) as pm25_std,
            round(max(fact.pm25_ug_m3)::numeric, 2) as pm25_max,
            round(percentile_cont(0.95) within group (order by fact.pm25_ug_m3)::numeric, 2) as pm25_p95
        from dwh.fact_air_quality_hourly as fact
        inner join dwh.dim_station as station on fact.station_key = station.station_key
        where fact.pm25_ug_m3 is not null
        group by station.station_name, station.district
        order by pm25_mean desc
        """
    )


def station_peak_days(limit: int = 20) -> pd.DataFrame:
    return read_sql(
        """
        select
            station_name,
            date_day,
            season,
            round(pm25_ug_m3_avg::numeric, 2) as pm25_day_avg,
            pm25_hour_count
        from mart.mart_station_daily
        where pm25_ug_m3_avg is not null
        order by pm25_ug_m3_avg desc
        limit %(limit)s
        """,
        {"limit": limit},
    )


def pollutant_overall_summary() -> pd.DataFrame:
    parts: list[str] = []
    for col, label in POLLUTANTS:
        parts.append(
            f"""
            select
                '{label}' as pollutant,
                count({col}) as n_non_null,
                round(avg({col})::numeric, 2) as mean_val,
                round(percentile_cont(0.5) within group (order by {col})::numeric, 2) as p50,
                round(percentile_cont(0.9) within group (order by {col})::numeric, 2) as p90,
                round(percentile_cont(0.95) within group (order by {col})::numeric, 2) as p95,
                round(max({col})::numeric, 2) as max_val
            from dwh.fact_air_quality_hourly
            where {col} is not null
            """
        )
    sql = " union all ".join(parts)
    return read_sql(sql)


def pollutant_by_season() -> pd.DataFrame:
    parts: list[str] = []
    for col, label in POLLUTANTS:
        parts.append(
            f"""
            select
                calendar.season,
                '{label}' as pollutant,
                round(avg(fact.{col})::numeric, 2) as mean_val,
                count(fact.{col}) as n
            from dwh.fact_air_quality_hourly as fact
            inner join dwh.dim_date as calendar on fact.date_key = calendar.date_key
            where fact.{col} is not null
            group by calendar.season
            """
        )
    sql = " union all ".join(parts) + " order by pollutant, season"
    return read_sql(sql)


def pollutant_correlation_sample(sample_size: int = 50_000) -> pd.DataFrame:
    """Random sample of pollutant columns for pairwise correlation in pandas."""
    return read_sql(
        """
        select
            pm25_ug_m3, pm10_ug_m3, so2_ug_m3, no2_ug_m3, co_ug_m3, o3_ug_m3
        from dwh.fact_air_quality_hourly
        where pm25_ug_m3 is not null
        order by random()
        limit %(sample_size)s
        """,
        {"sample_size": sample_size},
    )


def weather_vs_pm25_bins() -> pd.DataFrame:
    return read_sql(
        """
        select
            width_bucket(temperature_c, -20, 40, 6) as temp_bin,
            round(avg(temperature_c)::numeric, 2) as temp_avg,
            round(avg(pm25_ug_m3)::numeric, 2) as pm25_avg,
            count(*) as n
        from dwh.fact_air_quality_hourly
        where temperature_c is not null and pm25_ug_m3 is not null
        group by 1
        order by 1
        """
    )


def weather_vs_pm25_wind() -> pd.DataFrame:
    return read_sql(
        """
        select
            width_bucket(wind_speed_m_s, 0, 12, 6) as wind_bin,
            round(avg(wind_speed_m_s)::numeric, 2) as wind_avg,
            round(avg(pm25_ug_m3)::numeric, 2) as pm25_avg,
            count(*) as n
        from dwh.fact_air_quality_hourly
        where wind_speed_m_s is not null and pm25_ug_m3 is not null
        group by 1
        order by 1
        """
    )


def weather_vs_pm25_rh() -> pd.DataFrame:
    return read_sql(
        """
        select
            width_bucket(relative_humidity_pct, 0, 100, 5) as rh_bin,
            round(avg(relative_humidity_pct)::numeric, 2) as rh_avg,
            round(avg(pm25_ug_m3)::numeric, 2) as pm25_avg,
            count(*) as n
        from dwh.fact_air_quality_hourly
        where relative_humidity_pct is not null and pm25_ug_m3 is not null
        group by 1
        order by 1
        """
    )


def weather_pm25_correlations(sample_size: int = 50_000) -> pd.DataFrame:
    return read_sql(
        """
        select
            pm25_ug_m3,
            temperature_c,
            relative_humidity_pct,
            wind_speed_m_s,
            pressure_hpa,
            rain_mm,
            cloud_cover_pct,
            dew_point_c
        from dwh.fact_air_quality_hourly
        where pm25_ug_m3 is not null
        order by random()
        limit %(sample_size)s
        """,
        {"sample_size": sample_size},
    )


def data_quality_overview() -> pd.DataFrame:
    return read_sql(
        """
        select
            data_quality_status,
            count(*) as row_count,
            round(100.0 * count(*) / sum(count(*)) over (), 2) as pct
        from dwh.fact_air_quality_hourly
        group by data_quality_status
        order by row_count desc
        """
    )


def missing_rates_by_station() -> pd.DataFrame:
    return read_sql(
        """
        select
            station.station_name,
            count(*) as hour_count,
            round(100.0 * count(*) filter (where fact.pm25_ug_m3 is null) / count(*), 2) as pm25_missing_pct,
            round(100.0 * count(*) filter (where fact.has_missing_pollutant) / count(*), 2) as any_pollutant_missing_pct,
            round(100.0 * count(*) filter (where fact.has_missing_weather) / count(*), 2) as weather_missing_pct,
            round(100.0 * count(*) filter (where fact.suspect_cap) / count(*), 2) as suspect_cap_pct
        from dwh.fact_air_quality_hourly as fact
        inner join dwh.dim_station as station on fact.station_key = station.station_key
        group by station.station_name
        order by pm25_missing_pct desc
        """
    )


def weather_source_mix() -> pd.DataFrame:
    return read_sql(
        """
        select
            coalesce(temperature_source, 'null') as temperature_source,
            count(*) as n,
            round(100.0 * count(*) / sum(count(*)) over (), 2) as pct
        from dwh.fact_air_quality_hourly
        group by 1
        order by n desc
        """
    )


def global_pm25_percentiles() -> dict[str, Any]:
    df = read_sql(
        """
        select
            round(percentile_cont(0.5) within group (order by pm25_ug_m3)::numeric, 2) as p50,
            round(percentile_cont(0.75) within group (order by pm25_ug_m3)::numeric, 2) as p75,
            round(percentile_cont(0.9) within group (order by pm25_ug_m3)::numeric, 2) as p90,
            round(percentile_cont(0.95) within group (order by pm25_ug_m3)::numeric, 2) as p95,
            round(avg(pm25_ug_m3)::numeric, 2) as mean_val,
            count(pm25_ug_m3) as n
        from dwh.fact_air_quality_hourly
        where pm25_ug_m3 is not null
        """
    )
    return df.iloc[0].to_dict()
