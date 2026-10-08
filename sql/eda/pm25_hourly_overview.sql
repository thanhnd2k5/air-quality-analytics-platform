-- PM2.5 by season from the hourly fact (baseline for temporal EDA).
select
    calendar.season,
    count(*) as hour_count,
    count(fact.pm25_ug_m3) as pm25_hour_count,
    round(avg(fact.pm25_ug_m3)::numeric, 2) as pm25_avg,
    round(percentile_cont(0.5) within group (order by fact.pm25_ug_m3)::numeric, 2) as pm25_p50,
    round(percentile_cont(0.9) within group (order by fact.pm25_ug_m3)::numeric, 2) as pm25_p90,
    round(percentile_cont(0.95) within group (order by fact.pm25_ug_m3)::numeric, 2) as pm25_p95
from dwh.fact_air_quality_hourly as fact
inner join dwh.dim_date as calendar
    on fact.date_key = calendar.date_key
group by calendar.season
order by calendar.season;
