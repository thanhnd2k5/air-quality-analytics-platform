select station_key, date_key, 'daily' as mart_name
from {{ ref('mart_station_daily') }}
where pm25_hour_count > hour_count
    or (pm25_ug_m3_avg is null) is distinct from (pm25_hour_count = 0)
    or (temperature_c_avg is null) is distinct from (temperature_hour_count = 0)
    or (rain_mm_sum is null) is distinct from (rain_hour_count = 0)

union all

select station_key, year * 100 + month, 'monthly'
from {{ ref('mart_station_monthly') }}
where pm25_hour_count > hour_count
    or (pm25_ug_m3_avg is null) is distinct from (pm25_hour_count = 0)
    or (temperature_c_avg is null) is distinct from (temperature_hour_count = 0)
    or (rain_mm_sum is null) is distinct from (rain_hour_count = 0)

union all

select station_key, date_key, 'pollution_weather'
from {{ ref('mart_pollution_weather') }}
where pm25_hour_count > hour_count
    or (pm25_ug_m3_avg is null) is distinct from (pm25_hour_count = 0)
    or (temperature_c_avg is null) is distinct from (temperature_hour_count = 0)
    or (rain_mm_sum is null) is distinct from (rain_hour_count = 0)
