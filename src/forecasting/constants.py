"""Locked Phase 10 forecasting constants (split, window, feature set)."""

from __future__ import annotations

# ML chronological window (exclude partial 2017 from primary train/val/test).
ML_START = "2013-03-01 00:00:00"
ML_END = "2016-12-31 23:00:00"

# Locked split (P10 plan).
TRAIN_END = "2015-12-31 23:00:00"
VAL_START = "2016-01-01 00:00:00"
VAL_END = "2016-06-30 23:00:00"
TEST_START = "2016-07-01 00:00:00"
TEST_END = "2016-12-31 23:00:00"

EXPECTED_STATIONS = 12
EXPECTED_CLUSTERS = 2

PM25_LAGS = (1, 2, 3, 6, 12, 24)
PM25_ROLL_WINDOWS = (6, 24)
WEATHER_COLS = (
    "temperature_c",
    "relative_humidity_pct",
    "wind_speed_m_s",
)
WEATHER_LAG = 1

# Vòng A (feature v2): co-pollutants + causal episode (EDA lock ≥115 / ≥3h).
POLLUTANT_COLS = (
    "pm10_ug_m3",
    "co_ug_m3",
    "no2_ug_m3",
)
POLLUTANT_LAGS = (1, 2, 3, 6)
EPISODE_THRESHOLD = 115.0
EPISODE_MIN_HOURS = 3
SAMPLE_WEIGHT_THRESHOLD = 115.0
SAMPLE_WEIGHT_HIGH = 2.0

# Columns used as model inputs after impute (P10c may one-hot season/station).
# pm25_ug_m3 = value at prediction origin t (valid nowcast input; also persistence baseline).
FEATURE_COLS = (
    "hour",
    "month",
    "day_of_week",
    "season_code",
    "station_key",
    "cluster_id",
    "pm25_ug_m3",
    *(f"pm25_lag_{k}" for k in PM25_LAGS),
    *(f"pm25_roll_mean_{w}" for w in PM25_ROLL_WINDOWS),
    *WEATHER_COLS,
    *(f"{c}_lag_{WEATHER_LAG}" for c in WEATHER_COLS),
    *(f"{c}_missing" for c in WEATHER_COLS),
)

# Vòng A feature set (does not replace FEATURE_COLS / production lock).
FEATURE_COLS_V2 = (
    *FEATURE_COLS,
    "pm25_delta_1",
    *POLLUTANT_COLS,
    *(f"{c}_lag_{k}" for c in POLLUTANT_COLS for k in POLLUTANT_LAGS),
    *(f"{c}_missing" for c in POLLUTANT_COLS),
    "hours_into_episode",
    "in_episode_flag",
)

# Vòng B-feature (v3): O3/SO2 + cloud_cover on top of v2 (does not replace v2 lock).
POLLUTANT_COLS_V3 = (
    *POLLUTANT_COLS,
    "o3_ug_m3",
    "so2_ug_m3",
)
WEATHER_COLS_V3 = (
    *WEATHER_COLS,
    "cloud_cover_pct",
)
FEATURE_COLS_V3 = (
    *FEATURE_COLS_V2,
    "o3_ug_m3",
    "so2_ug_m3",
    *(f"{c}_lag_{k}" for c in ("o3_ug_m3", "so2_ug_m3") for k in POLLUTANT_LAGS),
    "o3_ug_m3_missing",
    "so2_ug_m3_missing",
    "cloud_cover_pct",
    f"cloud_cover_pct_lag_{WEATHER_LAG}",
    "cloud_cover_pct_missing",
)

TARGET_COL = "y_pm25_tplus1"
META_COLS = (
    "station_key",
    "event_time_local",
    "target_time_local",
    "split",
    "cluster_label",
    "pm25_ug_m3",
    "season",
)

# LSTM experiment (Vòng B): slim per-timestep features — no lag/roll (encoded by window).
LSTM_SEQ_LEN = 24
LSTM_HIDDEN = 64
LSTM_DROPOUT = 0.1
LSTM_STATION_EMB_DIM = 8
LSTM_SEQ_COLS = (
    "pm25_ug_m3",
    *WEATHER_COLS,
    *POLLUTANT_COLS,
    "hours_into_episode",
    "in_episode_flag",
    "hour",
    "month",
    "day_of_week",
    "season_code",
    "cluster_id",
)

SEASON_TO_CODE = {
    "winter": 0,
    "spring": 1,
    "summer": 2,
    "autumn": 3,
}
