select
    station_key,
    event_time_local,
    data_quality_status
from {{ ref('fact_air_quality_hourly') }}
where has_missing_pollutant is distinct from (
        pm25_ug_m3 is null
        or pm10_ug_m3 is null
        or so2_ug_m3 is null
        or no2_ug_m3 is null
        or co_ug_m3 is null
        or o3_ug_m3 is null
    )
    or has_missing_weather is distinct from (
        temperature_c is null
        or pressure_hpa is null
        or dew_point_c is null
        or rain_mm is null
        or wind_speed_m_s is null
        or wind_direction is null
    )
    or (
        suspect_cap
        and data_quality_status is distinct from 'SUSPECT_CAP'
    )
    or (
        not suspect_cap
        and (has_missing_pollutant or has_missing_weather)
        and data_quality_status is distinct from 'MISSING_MEASUREMENT'
    )
    or (
        not suspect_cap
        and not has_missing_pollutant
        and not has_missing_weather
        and data_quality_status is distinct from 'OK'
    )
