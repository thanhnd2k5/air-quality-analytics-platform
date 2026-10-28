-- Station-day slice used to compare pollution with resolved weather.
select
    fact.station_key,
    station.station_name,
    fact.date_key,
    calendar.date_day,
    calendar.season,
    count(*) as hour_count,
    count(fact.pm25_ug_m3) as pm25_hour_count,
    avg(fact.pm25_ug_m3) as pm25_ug_m3_avg,
    count(fact.pm10_ug_m3) as pm10_hour_count,
    avg(fact.pm10_ug_m3) as pm10_ug_m3_avg,
    count(fact.o3_ug_m3) as o3_hour_count,
    avg(fact.o3_ug_m3) as o3_ug_m3_avg,
    count(fact.temperature_c) as temperature_hour_count,
    avg(fact.temperature_c) as temperature_c_avg,
    count(fact.relative_humidity_pct) as relative_humidity_hour_count,
    avg(fact.relative_humidity_pct) as relative_humidity_pct_avg,
    count(fact.wind_speed_m_s) as wind_speed_hour_count,
    avg(fact.wind_speed_m_s) as wind_speed_m_s_avg,
    count(fact.pressure_hpa) as pressure_hour_count,
    avg(fact.pressure_hpa) as pressure_hpa_avg,
    count(fact.dew_point_c) as dew_point_hour_count,
    avg(fact.dew_point_c) as dew_point_c_avg,
    count(fact.cloud_cover_pct) as cloud_cover_hour_count,
    avg(fact.cloud_cover_pct) as cloud_cover_pct_avg,
    count(fact.rain_mm) as rain_hour_count,
    sum(fact.rain_mm) as rain_mm_sum
from {{ ref('fact_air_quality_hourly') }} as fact
inner join {{ ref('dim_station') }} as station
    on fact.station_key = station.station_key
inner join {{ ref('dim_date') }} as calendar
    on fact.date_key = calendar.date_key
group by
    fact.station_key,
    station.station_name,
    fact.date_key,
    calendar.date_day,
    calendar.season
