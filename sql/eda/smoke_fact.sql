-- Phase 8 kickoff: confirm fact grain and time span (expect 420768 rows, 12 stations).
select
    count(*)::bigint as row_count,
    count(distinct station_key)::int as station_count,
    min(event_time_local) as min_event_time,
    max(event_time_local) as max_event_time,
    count(pm25_ug_m3)::bigint as pm25_non_null
from dwh.fact_air_quality_hourly;
