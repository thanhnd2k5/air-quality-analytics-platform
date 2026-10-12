-- Fail if duplicate station_key × prediction_origin_time in the alert mart.
select
    station_key,
    prediction_origin_time,
    count(*) as row_count
from {{ ref('mart_pm25_alerts') }}
group by station_key, prediction_origin_time
having count(*) > 1
