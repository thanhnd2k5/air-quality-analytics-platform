with bounds as (
    select
        min(event_time_local)::date as start_date,
        max(event_time_local)::date as end_date
    from {{ ref('stg_air_quality') }}
),
days as (
    select generate_series(start_date, end_date, interval '1 day')::date as date_day
    from bounds
)
select
    to_char(date_day, 'YYYYMMDD')::integer as date_key,
    date_day,
    extract(year from date_day)::integer as year,
    extract(quarter from date_day)::integer as quarter,
    extract(month from date_day)::integer as month,
    case extract(month from date_day)::integer
        when 1 then 'January'
        when 2 then 'February'
        when 3 then 'March'
        when 4 then 'April'
        when 5 then 'May'
        when 6 then 'June'
        when 7 then 'July'
        when 8 then 'August'
        when 9 then 'September'
        when 10 then 'October'
        when 11 then 'November'
        else 'December'
    end as month_name,
    extract(day from date_day)::integer as day_of_month,
    extract(isodow from date_day)::integer as day_of_week,
    case extract(isodow from date_day)::integer
        when 1 then 'Monday'
        when 2 then 'Tuesday'
        when 3 then 'Wednesday'
        when 4 then 'Thursday'
        when 5 then 'Friday'
        when 6 then 'Saturday'
        else 'Sunday'
    end as day_name,
    extract(isoyear from date_day)::integer as iso_year,
    extract(week from date_day)::integer as week_of_year,
    case
        when extract(month from date_day) in (12, 1, 2) then 'winter'
        when extract(month from date_day) in (3, 4, 5) then 'spring'
        when extract(month from date_day) in (6, 7, 8) then 'summer'
        else 'autumn'
    end as season
from days
