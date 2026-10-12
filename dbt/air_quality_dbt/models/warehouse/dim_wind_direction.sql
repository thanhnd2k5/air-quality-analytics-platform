-- One row per 16-point compass direction (UCI `wd` labels) + an UNKNOWN member (key 0)
-- so the fact never carries a null foreign key.
-- Concept hierarchy: wind_direction (16) → wind_quadrant (4 × 90°, starting at N) → wind_regime (2).
-- Regime: northerly = NE + NW quadrants (dry, cleaner air from Mongolia),
--         southerly = SE + SW quadrants (humid air from the Hebei plain).
with points as (
    select
        (point.ordinality - 1)::integer as sector_index,
        point.code,
        point.name_vi
    from unnest(
        array['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
              'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'],
        array['Bắc', 'Bắc Đông Bắc', 'Đông Bắc', 'Đông Đông Bắc',
              'Đông', 'Đông Đông Nam', 'Đông Nam', 'Nam Đông Nam',
              'Nam', 'Nam Tây Nam', 'Tây Nam', 'Tây Tây Nam',
              'Tây', 'Tây Tây Bắc', 'Tây Bắc', 'Bắc Tây Bắc']
    ) with ordinality as point(code, name_vi, ordinality)
)
select
    sector_index + 1 as wind_direction_key,
    code as wind_direction,
    name_vi as wind_direction_vi,
    sector_index * 22.5 as azimuth_deg,
    case sector_index / 4
        when 0 then 'NE'
        when 1 then 'SE'
        when 2 then 'SW'
        else 'NW'
    end as wind_quadrant,
    case sector_index / 4
        when 0 then 'Đông Bắc (0–90°)'
        when 1 then 'Đông Nam (90–180°)'
        when 2 then 'Tây Nam (180–270°)'
        else 'Tây Bắc (270–360°)'
    end as wind_quadrant_vi,
    case when sector_index / 4 in (0, 3) then 'northerly' else 'southerly' end as wind_regime,
    case when sector_index / 4 in (0, 3) then 'Gió bắc' else 'Gió nam' end as wind_regime_vi
from points

union all

select
    0 as wind_direction_key,
    'UNKNOWN' as wind_direction,
    'Không rõ' as wind_direction_vi,
    null::numeric as azimuth_deg,
    'UNKNOWN' as wind_quadrant,
    'Không rõ' as wind_quadrant_vi,
    'UNKNOWN' as wind_regime,
    'Không rõ' as wind_regime_vi
