"""Feature-matrix QC and leakage gates for Phase 10b / Vòng A v2."""

from __future__ import annotations

from typing import Any, Sequence

import pandas as pd

from src.forecasting.constants import (
    EXPECTED_CLUSTERS,
    EXPECTED_STATIONS,
    FEATURE_COLS,
    POLLUTANT_COLS_V3,
    TARGET_COL,
    WEATHER_COLS_V3,
)
from src.forecasting.features import (
    add_calendar_codes,
    add_causal_episode_features,
    add_pm25_delta,
    add_pm25_lags_and_rolls,
    add_pollutant_lags_and_missing_flags,
    add_target,
    add_weather_lags_and_missing_flags,
    leakage_spot_check,
)


def qc_feature_matrix(
    final: pd.DataFrame,
    *,
    build_meta: dict[str, Any],
    base_for_leakage: pd.DataFrame | None = None,
    feature_cols: Sequence[str] = FEATURE_COLS,
    phase: str = "P10b",
    variant: str = "v1",
) -> dict[str, Any]:
    """Return QC report; ok=False if hard gates fail."""
    issues: list[str] = []
    feature_cols = list(feature_cols)

    n_stations = int(final["station_key"].nunique())
    if n_stations != EXPECTED_STATIONS:
        issues.append(f"station_count={n_stations} expected={EXPECTED_STATIONS}")

    n_clusters = int(final["cluster_id"].nunique())
    if n_clusters != EXPECTED_CLUSTERS:
        issues.append(f"cluster_id_count={n_clusters} expected={EXPECTED_CLUSTERS}")

    if final[TARGET_COL].isna().any():
        issues.append("target has nulls after drop")
    if final["pm25_ug_m3"].isna().any():
        issues.append("pm25_ug_m3 (t) has nulls after drop")
    if final["pm25_lag_1"].isna().any():
        issues.append("pm25_lag_1 has nulls after drop")

    missing_feats = [c for c in feature_cols if c not in final.columns]
    if missing_feats:
        issues.append(f"missing feature cols: {missing_feats}")

    # Future leakage: feature names must not include target or obvious t+1 labels.
    bad_names = [
        c
        for c in final.columns
        if (c.endswith("_tplus1") and c != TARGET_COL) or ("future" in c.lower())
    ]
    if bad_names:
        issues.append(f"suspicious future-named columns: {bad_names}")

    split_counts = final["split"].value_counts().to_dict()
    for part in ("train", "val", "test"):
        if int(split_counts.get(part, 0)) <= 0:
            issues.append(f"split {part} is empty")

    # Chronological integrity within each station: time sorted, split order train≤val≤test
    chrono_ok = True
    for sk, sub in final.groupby("station_key"):
        times = sub["event_time_local"]
        if not times.is_monotonic_increasing:
            chrono_ok = False
            issues.append(f"station {sk} event_time not sorted")
            break
        # Max train time < min val time < ... when all present
        train_t = sub.loc[sub["split"] == "train", "event_time_local"]
        val_t = sub.loc[sub["split"] == "val", "event_time_local"]
        test_t = sub.loc[sub["split"] == "test", "event_time_local"]
        if len(train_t) and len(val_t) and train_t.max() >= val_t.min():
            chrono_ok = False
            issues.append(f"station {sk} train overlaps val")
            break
        if len(val_t) and len(test_t) and val_t.max() >= test_t.min():
            chrono_ok = False
            issues.append(f"station {sk} val overlaps test")
            break

    # Hard-gate: raw extract must be contiguous hourly per station (lag/roll are row-shifts).
    hour_grid_ok = True
    if base_for_leakage is not None and not base_for_leakage.empty:
        for sk, sub in base_for_leakage.groupby("station_key"):
            times = pd.to_datetime(sub["event_time_local"]).sort_values()
            if len(times) < 2:
                continue
            deltas = times.diff().dropna()
            bad = int((deltas != pd.Timedelta(hours=1)).sum())
            if bad > 0:
                hour_grid_ok = False
                issues.append(
                    f"station {sk}: {bad} non-1h gaps in extract (lags assume contiguous hours)"
                )
                break

    leakage_checks: list[dict[str, Any]] = []
    if base_for_leakage is not None and not base_for_leakage.empty:
        eng = add_calendar_codes(base_for_leakage)
        eng = add_pm25_lags_and_rolls(eng)
        if variant in ("v2", "v3"):
            eng = add_pm25_delta(eng)
            if variant == "v3":
                eng = add_pollutant_lags_and_missing_flags(
                    eng, pollutant_cols=POLLUTANT_COLS_V3
                )
                eng = add_weather_lags_and_missing_flags(
                    eng, weather_cols=WEATHER_COLS_V3
                )
            else:
                eng = add_pollutant_lags_and_missing_flags(eng)
                eng = add_weather_lags_and_missing_flags(eng)
            eng = add_causal_episode_features(eng)
        else:
            eng = add_weather_lags_and_missing_flags(eng)
        eng = add_target(eng)
        leakage_checks = leakage_spot_check(eng)
        required_keys = ["lag1_matches_prev_pm25", "target_matches_next_pm25"]
        if variant in ("v2", "v3"):
            required_keys += [
                "delta1_matches_pm25_minus_lag1",
                "episode_streak_matches_prefix",
            ]
        if not all(all(r.get(k, True) for k in required_keys) for r in leakage_checks):
            issues.append("leakage spot-check failed")

    # Null rates on features after impute (weather/pollutant should be low)
    null_rates = {
        c: float(final[c].isna().mean()) for c in feature_cols if c in final.columns
    }
    high_null = {c: r for c, r in null_rates.items() if r > 0.01}
    if high_null:
        issues.append(f"feature null rate >1%: {high_null}")

    ok = len(issues) == 0
    return {
        "ok": ok,
        "phase": phase,
        "variant": variant,
        "issues": issues,
        "row_count": int(len(final)),
        "station_count": n_stations,
        "cluster_id_count": n_clusters,
        "split_counts": {k: int(v) for k, v in split_counts.items()},
        "null_rates_features": null_rates,
        "chronological_split_ok": chrono_ok,
        "hour_grid_contiguous": hour_grid_ok,
        "leakage_spot_checks": leakage_checks,
        "build_meta": build_meta,
        "feature_cols": feature_cols,
    }
