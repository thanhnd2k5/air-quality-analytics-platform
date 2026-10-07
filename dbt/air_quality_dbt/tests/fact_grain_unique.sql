select
    station_key,
    date_key,
    time_key,
    count(*) as row_count
from {{ ref('fact_air_quality_hourly') }}
group by station_key, date_key, time_key
having count(*) > 1
