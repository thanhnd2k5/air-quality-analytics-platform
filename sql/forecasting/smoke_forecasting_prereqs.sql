-- Phase 10a: smoke fact + cluster mart join in ML window (read-only)
-- ML window: 2013-03-01 → 2016-12-31 (primary train/val/test; exclude 2017)

select
    count(*)::bigint as row_count,
    count(distinct fact.station_key)::int as station_count,
    min(fact.event_time_local) as min_event_time,
    max(fact.event_time_local) as max_event_time,
    count(fact.pm25_ug_m3)::bigint as pm25_non_null,
    count(cl.station_key)::bigint as cluster_joined_rows
from dwh.fact_air_quality_hourly as fact
left join mart.mart_station_cluster as cl
    on fact.station_key = cl.station_key
where fact.event_time_local >= timestamp '2013-03-01 00:00:00'
  and fact.event_time_local <= timestamp '2016-12-31 23:00:00';
