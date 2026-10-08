-- Grain: one station × one PM2.5 episode (locked Phase 8c definition).
-- dirty: pm25 >= threshold (null breaks run); episode length >= min_hours.
{% set threshold = var('pm25_episode_threshold', 115) %}
{% set min_hours = var('pm25_episode_min_hours', 3) %}

with fact as (
    select
        fact.station_key,
        station.station_name,
        fact.event_time_local,
        fact.pm25_ug_m3,
        fact.temperature_c,
        fact.relative_humidity_pct,
        fact.wind_speed_m_s,
        fact.rain_mm,
        fact.cloud_cover_pct,
        calendar.year,
        calendar.season,
        (
            fact.pm25_ug_m3 is not null
            and fact.pm25_ug_m3 >= {{ threshold }}
        ) as is_dirty
    from {{ ref('fact_air_quality_hourly') }} as fact
    inner join {{ ref('dim_station') }} as station
        on fact.station_key = station.station_key
    inner join {{ ref('dim_date') }} as calendar
        on fact.date_key = calendar.date_key
),
numbered as (
    select
        *,
        row_number() over (
            partition by station_key
            order by event_time_local
        ) as rn,
        row_number() over (
            partition by station_key, is_dirty
            order by event_time_local
        ) as rn_dirty_flag
    from fact
),
islanded as (
    select
        *,
        case
            when is_dirty then rn - rn_dirty_flag
        end as island_grp
    from numbered
),
episodes as (
    select
        station_key,
        station_name,
        island_grp,
        min(event_time_local) as start_time,
        max(event_time_local) as end_time,
        count(*)::integer as duration_hours,
        avg(pm25_ug_m3) as pm25_mean,
        max(pm25_ug_m3) as pm25_max,
        (array_agg(year order by event_time_local))[1] as year,
        (array_agg(season order by event_time_local))[1] as season,
        avg(temperature_c) as temperature_c_avg,
        avg(relative_humidity_pct) as relative_humidity_pct_avg,
        avg(wind_speed_m_s) as wind_speed_m_s_avg,
        sum(coalesce(rain_mm, 0)) as rain_mm_sum,
        avg(cloud_cover_pct) as cloud_cover_pct_avg
    from islanded
    where is_dirty
    group by station_key, station_name, island_grp
    having count(*) >= {{ min_hours }}
)
select
    row_number() over (
        order by station_key, start_time
    )::integer as episode_id,
    station_key,
    station_name,
    start_time,
    end_time,
    duration_hours,
    pm25_mean,
    pm25_max,
    year,
    season,
    temperature_c_avg,
    relative_humidity_pct_avg,
    wind_speed_m_s_avg,
    rain_mm_sum,
    cloud_cover_pct_avg,
    {{ threshold }}::double precision as threshold_ug_m3,
    {{ min_hours }}::integer as min_hours
from episodes
