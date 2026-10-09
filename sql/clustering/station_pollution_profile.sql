-- Phase 9b: one row per station — pollution profile for clustering.
-- Window: 2013-03-01 00:00 → 2016-12-31 23:00 (exclude partial 2017).
-- Grain: station_key. Season from dwh.dim_date (same as Phase 8).
-- Episode stats: overlap profile window; duration clipped to [start_ts, end_ts]
-- (feature set v1_1_episode_window_clip).

-- Bounds injected from src.clustering.smoke PROFILE_START / PROFILE_END
-- via load_profile_sql() placeholders (keep in sync — do not hardcode elsewhere).
with bounds as (
    select
        timestamp '__PROFILE_START__' as start_ts,
        timestamp '__PROFILE_END__' as end_ts
),
fact_w as (
    select
        fact.station_key,
        station.station_name,
        station.district,
        fact.event_time_local,
        calendar.season,
        fact.pm25_ug_m3,
        fact.pm10_ug_m3,
        fact.no2_ug_m3,
        fact.co_ug_m3,
        fact.so2_ug_m3,
        fact.o3_ug_m3
    from dwh.fact_air_quality_hourly as fact
    inner join dwh.dim_station as station
        on fact.station_key = station.station_key
    inner join dwh.dim_date as calendar
        on fact.date_key = calendar.date_key
    cross join bounds
    where fact.event_time_local >= bounds.start_ts
      and fact.event_time_local <= bounds.end_ts
),
pollutant as (
    select
        station_key,
        station_name,
        district,
        count(*)::bigint as hour_count,
        count(pm25_ug_m3)::bigint as pm25_hour_count,
        round(avg(pm25_ug_m3)::numeric, 4) as mean_pm25,
        round(
            percentile_cont(0.5) within group (order by pm25_ug_m3)::numeric,
            4
        ) as median_pm25,
        round(stddev_samp(pm25_ug_m3)::numeric, 4) as std_pm25,
        round(avg(pm10_ug_m3)::numeric, 4) as mean_pm10,
        round(avg(no2_ug_m3)::numeric, 4) as mean_no2,
        round(avg(co_ug_m3)::numeric, 4) as mean_co,
        round(avg(so2_ug_m3)::numeric, 4) as mean_so2,
        round(avg(o3_ug_m3)::numeric, 4) as mean_o3,
        round(
            (
                100.0 * count(*) filter (
                    where pm25_ug_m3 is not null and pm25_ug_m3 >= 75
                )
                / nullif(count(pm25_ug_m3), 0)
            )::numeric,
            4
        ) as pct_hours_pm25_ge_75,
        round(
            (
                100.0 * count(*) filter (
                    where pm25_ug_m3 is not null and pm25_ug_m3 >= 115
                )
                / nullif(count(pm25_ug_m3), 0)
            )::numeric,
            4
        ) as pct_hours_pm25_ge_115
    from fact_w
    group by station_key, station_name, district
),
seasonal as (
    select
        station_key,
        round(
            avg(pm25_ug_m3) filter (where season = 'spring')::numeric,
            4
        ) as mean_pm25_spring,
        round(
            avg(pm25_ug_m3) filter (where season = 'summer')::numeric,
            4
        ) as mean_pm25_summer,
        round(
            avg(pm25_ug_m3) filter (where season = 'autumn')::numeric,
            4
        ) as mean_pm25_autumn,
        round(
            avg(pm25_ug_m3) filter (where season = 'winter')::numeric,
            4
        ) as mean_pm25_winter
    from fact_w
    where pm25_ug_m3 is not null
    group by station_key
),
episodes as (
    select
        ep.station_key,
        count(*)::integer as episode_count,
        round(avg(clipped.hours_in_window)::numeric, 4) as mean_episode_duration_h,
        sum(clipped.hours_in_window)::integer as total_episode_hours
    from mart.mart_pm25_episodes as ep
    cross join bounds
    cross join lateral (
        select
            (
                extract(
                    epoch from (
                        least(ep.end_time, bounds.end_ts)
                        - greatest(ep.start_time, bounds.start_ts)
                    )
                )
                / 3600
            )::integer
            + 1 as hours_in_window
    ) as clipped
    where ep.start_time <= bounds.end_ts
      and ep.end_time >= bounds.start_ts
      and clipped.hours_in_window > 0
    group by ep.station_key
)
select
    p.station_key,
    p.station_name,
    p.district,
    p.hour_count,
    p.pm25_hour_count,
    p.mean_pm25,
    p.median_pm25,
    p.std_pm25,
    p.mean_pm10,
    p.mean_no2,
    p.mean_co,
    p.mean_so2,
    p.mean_o3,
    s.mean_pm25_spring,
    s.mean_pm25_summer,
    s.mean_pm25_autumn,
    s.mean_pm25_winter,
    p.pct_hours_pm25_ge_75,
    p.pct_hours_pm25_ge_115,
    coalesce(e.episode_count, 0) as episode_count,
    coalesce(e.mean_episode_duration_h, 0) as mean_episode_duration_h,
    coalesce(e.total_episode_hours, 0) as total_episode_hours
from pollutant as p
inner join seasonal as s
    on p.station_key = s.station_key
left join episodes as e
    on p.station_key = e.station_key
order by p.mean_pm25 desc nulls last;
