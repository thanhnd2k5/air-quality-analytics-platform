select
    station_id as station_key,
    station_code,
    station_name,
    latitude,
    longitude,
    district,
    coordinate_status
from {{ ref('stg_station') }}
