-- Each of the 32 cuboids in mart_olap_cube is a full partition of the fact:
-- its cells must add back to the fact's row count and PM2.5 sum. Also exactly 32 cuboids.
with fact_totals as (
    select count(*) as hour_count, sum(pm25_ug_m3) as pm25_sum
    from {{ ref('fact_air_quality_hourly') }}
),
cuboid_totals as (
    select grouping_id, sum(hour_count) as hour_count, sum(pm25_sum) as pm25_sum
    from {{ ref('mart_olap_cube') }}
    group by grouping_id
)
select c.grouping_id, c.hour_count, f.hour_count as fact_hour_count
from cuboid_totals as c
cross join fact_totals as f
where c.hour_count <> f.hour_count
    or abs(c.pm25_sum - f.pm25_sum) > 1e-6 * f.pm25_sum

union all

select null, count(*), 32
from cuboid_totals
having count(*) <> 32
