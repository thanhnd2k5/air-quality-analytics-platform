-- Grain: one station × one hour. Weather columns are resolved (UCI, else Open-Meteo).
-- Dimensions: dim_station, dim_date, dim_time, dim_wind_direction (key 0 = UNKNOWN).
select
    station.station_key,
    to_char(hour_row.event_time_local, 'YYYYMMDD')::integer as date_key,
    extract(hour from hour_row.event_time_local)::integer as time_key,
    coalesce(wind.wind_direction_key, 0) as wind_direction_key,
    hour_row.event_time_local,
    hour_row.pm25_ug_m3,
    hour_row.pm10_ug_m3,
    hour_row.so2_ug_m3,
    hour_row.no2_ug_m3,
    hour_row.co_ug_m3,
    hour_row.o3_ug_m3,
    hour_row.temperature_c,
    hour_row.temperature_source,
    hour_row.pressure_hpa,
    hour_row.pressure_source,
    hour_row.dew_point_c,
    hour_row.dew_point_source,
    hour_row.rain_mm,
    hour_row.rain_source,
    hour_row.wind_speed_m_s,
    hour_row.wind_speed_source,
    hour_row.wind_direction,
    hour_row.wind_direction_source,
    hour_row.cloud_cover_pct,
    hour_row.relative_humidity_pct,
    hour_row.has_missing_pollutant,
    hour_row.has_missing_weather,
    hour_row.suspect_cap,
    hour_row.data_quality_status
from {{ ref('int_station_hour') }} as hour_row
inner join {{ ref('dim_station') }} as station
    on hour_row.station_name = station.station_name
left join {{ ref('dim_wind_direction') }} as wind
    on hour_row.wind_direction = wind.wind_direction
