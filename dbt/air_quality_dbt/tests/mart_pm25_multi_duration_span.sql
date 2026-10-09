-- Contiguous hourly grain: multi-station event duration must match inclusive span.
select
    event_id,
    start_time,
    end_time,
    duration_hours,
    (extract(epoch from (end_time - start_time)) / 3600)::integer + 1 as expected_duration_hours
from {{ ref('mart_pm25_multi_station_events') }}
where duration_hours
    <> (extract(epoch from (end_time - start_time)) / 3600)::integer + 1
