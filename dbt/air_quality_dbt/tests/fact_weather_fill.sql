select
    station.station_name,
    fact.event_time_local
from {{ ref('fact_air_quality_hourly') }} as fact
inner join {{ ref('dim_station') }} as station
    on fact.station_key = station.station_key
inner join {{ source('staging', 'air_quality_hourly') }} as air
    on air.station_name = station.station_name
    and air.event_time_local = fact.event_time_local
left join {{ source('staging', 'weather_openmeteo_hourly') }} as om
    on om.station_name = air.station_name
    and om.event_time_local = air.event_time_local
where air.pm25_ug_m3 is distinct from fact.pm25_ug_m3
    or (
        air.temperature_c is not null
        and fact.temperature_c is distinct from air.temperature_c
    )
    or (
        air.temperature_c is null
        and om.om_temperature_c is not null
        and (
            fact.temperature_source is distinct from 'openmeteo'
            or fact.temperature_c is distinct from om.om_temperature_c
        )
    )
    or (
        air.temperature_c is null
        and om.om_temperature_c is null
        and fact.temperature_c is not null
    )
