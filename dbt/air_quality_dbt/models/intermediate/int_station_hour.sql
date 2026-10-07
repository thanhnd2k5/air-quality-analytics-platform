-- One row per station-hour. Weather is resolved here; pollutants are not filled.
-- Quality flags describe this resolved row. UCI flags stay on stg_air_quality.
with resolved as (
    select
        air.station_name,
        air.event_time_local,
        air.pm25_ug_m3,
        air.pm10_ug_m3,
        air.so2_ug_m3,
        air.no2_ug_m3,
        air.co_ug_m3,
        air.o3_ug_m3,
        {{ resolve_numeric('air.temperature_c', 'om.om_temperature_c') }} as temperature_c,
        {{ resolve_source('air.temperature_c', 'om.om_temperature_c') }} as temperature_source,
        {{ resolve_numeric('air.pressure_hpa', 'om.om_surface_pressure_hpa') }} as pressure_hpa,
        {{ resolve_source('air.pressure_hpa', 'om.om_surface_pressure_hpa') }} as pressure_source,
        {{ resolve_numeric('air.dew_point_c', 'om.om_dew_point_c') }} as dew_point_c,
        {{ resolve_source('air.dew_point_c', 'om.om_dew_point_c') }} as dew_point_source,
        {{ resolve_numeric('air.rain_mm', 'om.om_rain_mm') }} as rain_mm,
        {{ resolve_source('air.rain_mm', 'om.om_rain_mm') }} as rain_source,
        {{ resolve_numeric('air.wind_speed_m_s', 'om.om_wind_speed_m_s') }} as wind_speed_m_s,
        {{ resolve_source('air.wind_speed_m_s', 'om.om_wind_speed_m_s') }} as wind_speed_source,
        case
            when air.wind_direction is not null then air.wind_direction
            else {{ compass_16('om.om_wind_direction_deg') }}
        end as wind_direction,
        case
            when air.wind_direction is not null then 'uci'
            when om.om_wind_direction_deg is not null then 'openmeteo'
            else null
        end as wind_direction_source,
        om.om_cloud_cover_pct as cloud_cover_pct,
        {{ relative_humidity_pct(
            resolve_numeric('air.temperature_c', 'om.om_temperature_c'),
            resolve_numeric('air.dew_point_c', 'om.om_dew_point_c')
        ) }} as relative_humidity_pct,
        air.suspect_cap
    from {{ ref('stg_air_quality') }} as air
    left join {{ ref('stg_weather_openmeteo') }} as om
        on air.station_name = om.station_name
        and air.event_time_local = om.event_time_local
),
flagged as (
    select
        resolved.*,
        (
            pm25_ug_m3 is null
            or pm10_ug_m3 is null
            or so2_ug_m3 is null
            or no2_ug_m3 is null
            or co_ug_m3 is null
            or o3_ug_m3 is null
        ) as has_missing_pollutant,
        (
            temperature_c is null
            or pressure_hpa is null
            or dew_point_c is null
            or rain_mm is null
            or wind_speed_m_s is null
            or wind_direction is null
        ) as has_missing_weather
    from resolved
)
select
    flagged.*,
    case
        when suspect_cap then 'SUSPECT_CAP'
        when has_missing_pollutant or has_missing_weather then 'MISSING_MEASUREMENT'
        else 'OK'
    end as data_quality_status
from flagged
