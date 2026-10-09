-- Phase 9a: smoke fact grain in profile window (read-only)
select
    count(*)::bigint as row_count,
    count(distinct station_key)::int as station_count,
    min(event_time_local) as min_event_time,
    max(event_time_local) as max_event_time,
    count(pm25_ug_m3)::bigint as pm25_non_null
from dwh.fact_air_quality_hourly
where event_time_local >= timestamp '2013-03-01 00:00:00'
  and event_time_local <= timestamp '2016-12-31 23:00:00';
