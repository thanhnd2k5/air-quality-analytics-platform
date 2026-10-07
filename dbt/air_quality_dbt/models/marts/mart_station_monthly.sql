select
    fact.station_key,
    station.station_name,
    station.district,
    calendar.year,
    calendar.month,
    count(*) as hour_count,
    count(fact.pm25_ug_m3) as pm25_hour_count,
    avg(fact.pm25_ug_m3) as pm25_ug_m3_avg,
    count(fact.pm10_ug_m3) as pm10_hour_count,
    avg(fact.pm10_ug_m3) as pm10_ug_m3_avg,
    count(fact.so2_ug_m3) as so2_hour_count,
    avg(fact.so2_ug_m3) as so2_ug_m3_avg,
    count(fact.no2_ug_m3) as no2_hour_count,
    avg(fact.no2_ug_m3) as no2_ug_m3_avg,
    count(fact.co_ug_m3) as co_hour_count,
    avg(fact.co_ug_m3) as co_ug_m3_avg,
    count(fact.o3_ug_m3) as o3_hour_count,
    avg(fact.o3_ug_m3) as o3_ug_m3_avg,
    count(fact.temperature_c) as temperature_hour_count,
    avg(fact.temperature_c) as temperature_c_avg,
    count(fact.relative_humidity_pct) as relative_humidity_hour_count,
    avg(fact.relative_humidity_pct) as relative_humidity_pct_avg,
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
    station.district,
    calendar.year,
    calendar.month
