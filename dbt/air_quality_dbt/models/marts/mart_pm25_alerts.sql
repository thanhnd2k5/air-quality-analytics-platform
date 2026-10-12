-- Grain: one alert decision per station × origin hour (t). Target: PM2.5 at t+1 ≥ alert_threshold.
-- Source: staging.pm25_alert_predictions_raw (locked classifier from scripts/run_classification.py).
-- outcome: TP/FP/FN/TN of the locked model, so the confusion matrix is a GROUP BY away.

select
    pred.station_key,
    station.station_name,
    station.district,
    pred.prediction_origin_time,
    pred.target_time,
    pred.split,
    pred.pm25_at_origin,
    pred.actual_pm25,
    pred.actual_alert,
    pred.predicted_alert,
    pred.predicted_proba,
    pred.persistence_alert,
    case
        when pred.actual_alert = 1 and pred.predicted_alert = 1 then 'TP'
        when pred.actual_alert = 0 and pred.predicted_alert = 1 then 'FP'
        when pred.actual_alert = 1 and pred.predicted_alert = 0 then 'FN'
        else 'TN'
    end as outcome,
    case
        when pred.actual_alert = 1 and pred.persistence_alert = 1 then 'TP'
        when pred.actual_alert = 0 and pred.persistence_alert = 1 then 'FP'
        when pred.actual_alert = 1 and pred.persistence_alert = 0 then 'FN'
        else 'TN'
    end as persistence_outcome,
    pred.pm25_at_origin < pred.alert_threshold and pred.actual_alert = 1 as is_onset,
    pred.alert_threshold,
    pred.probability_cutoff,
    pred.model_version,
    pred.cluster_id
from {{ source('staging', 'pm25_alert_predictions_raw') }} as pred
inner join {{ ref('dim_station') }} as station
    on pred.station_key = station.station_key
