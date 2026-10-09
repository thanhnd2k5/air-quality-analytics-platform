-- Grain: one prediction per station × origin hour (t). Target is PM2.5 at t+1.
-- Source: staging.pm25_predictions_raw (loaded from locked HistGB predictions).

select
    pred.station_key,
    station.station_name,
    station.district,
    pred.prediction_origin_time,
    pred.target_time,
    pred.split,
    pred.actual_pm25,
    pred.predicted_pm25,
    pred.predicted_pm25_persistence,
    pred.absolute_error,
    pred.model_version,
    pred.cluster_id
from {{ source('staging', 'pm25_predictions_raw') }} as pred
inner join {{ ref('dim_station') }} as station
    on pred.station_key = station.station_key
