-- Peak concurrent stations must be at least K for a multi-station event.
select event_id, peak_station_count, multi_station_k
from {{ ref('mart_pm25_multi_station_events') }}
where peak_station_count < multi_station_k
