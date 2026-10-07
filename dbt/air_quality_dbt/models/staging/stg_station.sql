select
    station_id,
    station_code,
    station_name,
    latitude,
    longitude,
    district,
    coordinate_status
from {{ source('staging', 'station_reference') }}
