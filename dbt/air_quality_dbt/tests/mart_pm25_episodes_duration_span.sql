-- Contiguous hourly grain: duration_hours must equal inclusive hour span.
-- Fails if timeline gaps exist inside an island or start/end are inconsistent.
select
    episode_id,
    start_time,
    end_time,
    duration_hours,
    (extract(epoch from (end_time - start_time)) / 3600)::integer + 1 as expected_duration_hours
from {{ ref('mart_pm25_episodes') }}
where duration_hours
    <> (extract(epoch from (end_time - start_time)) / 3600)::integer + 1
