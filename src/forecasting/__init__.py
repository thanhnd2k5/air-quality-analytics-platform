"""Phase 10 – PM2.5 forecasting (t+1h).

Keep package import light: heavy sklearn model helpers are lazy so CDC serve
can import ``src.forecasting.cdc_serve`` without pulling training modules.
"""

from src.forecasting.constants import FEATURE_COLS, TARGET_COL

__all__ = [
    "FEATURE_COLS",
    "TARGET_COL",
    "assign_split",
    "build_feature_matrix",
    "choose_lock",
    "fetch_forecast_base",
    "qc_feature_matrix",
    "run_histgb",
    "run_linear",
    "run_persistence",
    "smoke_forecasting_prereqs",
]


def __getattr__(name: str):
    if name == "fetch_forecast_base":
        from src.forecasting.extract import fetch_forecast_base

        return fetch_forecast_base
    if name == "build_feature_matrix":
        from src.forecasting.features import build_feature_matrix

        return build_feature_matrix
    if name in {"choose_lock", "run_histgb", "run_linear", "run_persistence"}:
        from src.forecasting import models as _models

        return getattr(_models, name)
    if name == "qc_feature_matrix":
        from src.forecasting.qc import qc_feature_matrix

        return qc_feature_matrix
    if name == "smoke_forecasting_prereqs":
        from src.forecasting.smoke import smoke_forecasting_prereqs

        return smoke_forecasting_prereqs
    if name == "assign_split":
        from src.forecasting.split import assign_split

        return assign_split
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
