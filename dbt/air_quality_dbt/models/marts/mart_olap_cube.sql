-- Pre-computed data cube: GROUP BY CUBE over five dimension attributes
-- (year, season, district, day_part, wind_quadrant) → 2^5 = 32 cuboids in one table.
-- grouping_id is the Postgres GROUPING() bitmask (bit = 1 → that attribute is rolled up to ALL);
-- cuboid names the attributes that are kept, 'ALL' is the apex cuboid.
-- Measures stay distributive (sum, count) so any cell can be rolled up again;
-- pm25_avg is algebraic (sum / count) and must not be averaged across cells.
select
    grouping(calendar.year, calendar.season, station.district, tod.day_part, wind.wind_quadrant)
        as grouping_id,
    coalesce(
        nullif(
            concat_ws(
                ',',
                case when grouping(calendar.year) = 0 then 'year' end,
                case when grouping(calendar.season) = 0 then 'season' end,
                case when grouping(station.district) = 0 then 'district' end,
                case when grouping(tod.day_part) = 0 then 'day_part' end,
                case when grouping(wind.wind_quadrant) = 0 then 'wind_quadrant' end
            ),
            ''
        ),
        'ALL'
    ) as cuboid,
    calendar.year,
    calendar.season,
    station.district,
    tod.day_part,
    wind.wind_quadrant,
    count(*) as hour_count,
    count(fact.pm25_ug_m3) as pm25_hour_count,
    sum(fact.pm25_ug_m3) as pm25_sum,
    avg(fact.pm25_ug_m3) as pm25_avg,
    count(*) filter (where fact.pm25_ug_m3 >= {{ var('pm25_episode_threshold') }}) as pm25_exceed_hours
from {{ ref('fact_air_quality_hourly') }} as fact
inner join {{ ref('dim_date') }} as calendar
    on fact.date_key = calendar.date_key
inner join {{ ref('dim_station') }} as station
    on fact.station_key = station.station_key
inner join {{ ref('dim_time') }} as tod
    on fact.time_key = tod.time_key
inner join {{ ref('dim_wind_direction') }} as wind
    on fact.wind_direction_key = wind.wind_direction_key
group by cube (calendar.year, calendar.season, station.district, tod.day_part, wind.wind_quadrant)
