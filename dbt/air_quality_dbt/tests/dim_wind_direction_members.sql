-- 16 compass points + UNKNOWN, each quadrant holds exactly 4 points.
select 'member_count' as check_name, count(*) as value
from {{ ref('dim_wind_direction') }}
having count(*) <> 17

union all

select wind_quadrant, count(*)
from {{ ref('dim_wind_direction') }}
where wind_direction_key > 0
group by wind_quadrant
having count(*) <> 4
