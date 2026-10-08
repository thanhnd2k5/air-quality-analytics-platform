-- Every station episode must meet the locked min_hours rule.
select episode_id, duration_hours, min_hours
from {{ ref('mart_pm25_episodes') }}
where duration_hours < min_hours
