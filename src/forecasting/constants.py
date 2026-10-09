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

# Co-pollutant lags (Phase 8 correlations); lag-1 only to limit leakage surface.
POLLUTANT_LAG_COLS = (
    "pm10_ug_m3",
    "no2_ug_m3",
    "co_ug_m3",
)
POLLUTANT_LAG = 1

# Locked Phase 8c episode rule — used causally (history ≤ t only).
EPISODE_THRESHOLD_UG_M3 = 115.0
EPISODE_MIN_HOURS = 3

# Columns used as model inputs after impute (P10c may one-hot season/station).
# pm25_ug_m3 = value at prediction origin t (valid nowcast input; also persistence baseline).
# Feature set v1.1: + causal episode flags, pm25_delta_1, co-pollutant lag-1.
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
    "pm25_delta_1",
    *WEATHER_COLS,
    *(f"{c}_lag_{WEATHER_LAG}" for c in WEATHER_COLS),
    *(f"{c}_missing" for c in WEATHER_COLS),
    *(f"{c}_lag_{POLLUTANT_LAG}" for c in POLLUTANT_LAG_COLS),
    *(f"{c}_lag_{POLLUTANT_LAG}_missing" for c in POLLUTANT_LAG_COLS),
    "hours_into_dirty_run",
    "in_episode_flag",
    "hours_since_last_episode",
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

SEASON_TO_CODE = {
    "winter": 0,
    "spring": 1,
    "summer": 2,
    "autumn": 3,
}
