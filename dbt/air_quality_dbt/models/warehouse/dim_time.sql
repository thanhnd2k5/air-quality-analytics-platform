select
    hour as time_key,
    hour,
    lpad(hour::text, 2, '0') || ':00' as hour_label,
    case
        when hour between 0 and 5 then 'night'
        when hour between 6 and 11 then 'morning'
        when hour between 12 and 17 then 'afternoon'
        else 'evening'
    end as day_part
from generate_series(0, 23) as hour
