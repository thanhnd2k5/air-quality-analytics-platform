-- Grain: one row per station. Cluster assignment locked in Phase 9c
-- (seed station_cluster_assignment ← artifacts/clustering/cluster_lock.json).

select
    seed.station_key,
    station.station_name,
    station.district,
    seed.cluster_id,
    seed.cluster_label,
    seed.method,
    seed.k,
    seed.feature_set_version,
    seed.locked_at
from {{ ref('station_cluster_assignment') }} as seed
inner join {{ ref('dim_station') }} as station
    on seed.station_key = station.station_key
