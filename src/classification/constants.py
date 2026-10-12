"""Locked settings for the PM2.5 alert classifier."""

from __future__ import annotations

from src.forecasting.constants import EPISODE_THRESHOLD, FEATURE_COLS_V2

# Same threshold as the locked episode definition (artifacts/eda/episode_definition.md).
ALERT_THRESHOLD = EPISODE_THRESHOLD
HORIZON_HOURS = 1
ALERT_TARGET_COL = "y_alert"
TARGET_PM25_COL = "y_pm25_target"

# Inputs are exactly the regression v2 features: everything known at origin time t.
FEATURE_COLS = FEATURE_COLS_V2

RANDOM_STATE = 42

# Decision tree (Bài 8): information gain → criterion="entropy". Depth picked on val.
TREE_DEPTH_GRID = (3, 4, 5, 6, 8, 10)
TREE_MIN_SAMPLES_LEAF = 200

# Probability cut-off for alerting, picked on val (never on test).
THRESHOLD_GRID = tuple(round(0.20 + 0.05 * i, 2) for i in range(13))  # 0.20 … 0.80

# Lock rule: highest val F1 among learned models (baselines excluded).
LOCK_METRIC = "f1"

SENSITIVITY_HORIZONS = (1, 3, 6)

BASELINE_MODELS = ("majority", "persistence")
