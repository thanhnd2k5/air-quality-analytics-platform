-- Grain: one multi-station PM2.5 event window (locked Phase 8c).
-- Hours where >= K stations are inside a qualifying station episode.
{% set threshold = var('pm25_episode_threshold', 115) %}
{% set min_hours = var('pm25_episode_min_hours', 3) %}
{% set k = var('pm25_multi_station_k', 6) %}

with fact as (
    select
        fact.station_key,
        fact.event_time_local,
        (
            fact.pm25_ug_m3 is not null
            and fact.pm25_ug_m3 >= {{ threshold }}
        ) as is_dirty
    from {{ ref('fact_air_quality_hourly') }} as fact
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
qualifying_islands as (
    select
        station_key,
        island_grp
    from islanded
    where is_dirty
    group by station_key, island_grp
    having count(*) >= {{ min_hours }}
),
episode_hours as (
    select
        islanded.station_key,
        islanded.event_time_local
    from islanded
    inner join qualifying_islands as qual
        on islanded.station_key = qual.station_key
        and islanded.island_grp = qual.island_grp
    where islanded.is_dirty
),
timeline as (
    select distinct event_time_local
    from fact
),
counts as (
    select
        timeline.event_time_local,
        coalesce(count(distinct episode_hours.station_key), 0)::integer as n_stations_in_episode
    from timeline
    left join episode_hours
        on timeline.event_time_local = episode_hours.event_time_local
    group by timeline.event_time_local
),
flagged as (
    select
        event_time_local,
        n_stations_in_episode,
        (n_stations_in_episode >= {{ k }}) as is_active
    from counts
),
numbered_hours as (
    select
        *,
        row_number() over (order by event_time_local) as rn,
        row_number() over (
            partition by is_active
            order by event_time_local
        ) as rn_active_flag
    from flagged
),
islanded_hours as (
    select
        *,
        case
            when is_active then rn - rn_active_flag
        end as event_grp
    from numbered_hours
),
events as (
    select
        event_grp,
        min(event_time_local) as start_time,
        max(event_time_local) as end_time,
        count(*)::integer as duration_hours,
        max(n_stations_in_episode)::integer as peak_station_count,
        avg(n_stations_in_episode)::double precision as mean_station_count
    from islanded_hours
    where is_active
    group by event_grp
)
select
    row_number() over (order by start_time)::integer as event_id,
    start_time,
    end_time,
    duration_hours,
    peak_station_count,
    mean_station_count,
    {{ k }}::integer as multi_station_k,
    {{ threshold }}::double precision as threshold_ug_m3,
    {{ min_hours }}::integer as min_hours
from events
