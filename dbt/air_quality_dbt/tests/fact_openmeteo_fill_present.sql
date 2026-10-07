select count(*) as openmeteo_temperature_rows
from {{ ref('fact_air_quality_hourly') }}
having count(*) filter (where temperature_source = 'openmeteo') = 0
