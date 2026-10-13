-- Phase 10b: base rows for PM2.5(t+1h) feature matrix (read-only)
select
    fact.station_key,
    fact.event_time_local,
    fact.time_key as hour,
    calendar.month,
    calendar.day_of_week,
    calendar.season,
    fact.pm25_ug_m3,
    fact.pm10_ug_m3,
    fact.co_ug_m3,
    fact.no2_ug_m3,
    fact.o3_ug_m3,
    fact.so2_ug_m3,
    fact.temperature_c,
    fact.relative_humidity_pct,
    fact.wind_speed_m_s,
    fact.cloud_cover_pct,
    cl.cluster_id,
    cl.cluster_label
from dwh.fact_air_quality_hourly as fact
inner join dwh.dim_date as calendar
    on fact.date_key = calendar.date_key
inner join mart.mart_station_cluster as cl
    on fact.station_key = cl.station_key
where fact.event_time_local >= %(start)s::timestamp
  and fact.event_time_local <= %(end)s::timestamp
order by fact.station_key, fact.event_time_local;
