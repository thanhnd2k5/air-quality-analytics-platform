select count(*) as row_count
from {{ ref('fact_air_quality_hourly') }}
having count(*) <> 420768
