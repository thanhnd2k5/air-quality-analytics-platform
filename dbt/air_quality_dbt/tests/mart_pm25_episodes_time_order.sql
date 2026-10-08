-- Episode end must be on/after start.
select episode_id, start_time, end_time
from {{ ref('mart_pm25_episodes') }}
where end_time < start_time
