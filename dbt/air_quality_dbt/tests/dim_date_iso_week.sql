select date_day, year, iso_year, week_of_year
from {{ ref('dim_date') }}
where (
        month = 12
        and week_of_year = 1
        and iso_year is distinct from year + 1
    )
    or (
        month = 1
        and week_of_year >= 52
        and iso_year is distinct from year - 1
    )
    or (
        not (
            (month = 12 and week_of_year = 1)
            or (month = 1 and week_of_year >= 52)
        )
        and iso_year is distinct from year
    )
