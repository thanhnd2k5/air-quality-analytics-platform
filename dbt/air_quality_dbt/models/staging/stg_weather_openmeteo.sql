select
    station_name,
    event_time_local,
    om_temperature_c,
    om_dew_point_c,
    om_surface_pressure_hpa,
    om_rain_mm,
    om_wind_speed_m_s,
    om_wind_direction_deg,
    om_cloud_cover_pct
from {{ source('staging', 'weather_openmeteo_hourly') }}
