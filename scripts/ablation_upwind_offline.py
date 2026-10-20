#!/usr/bin/env python3
"""One-shot upwind ablation: M0 lock features, M2 nearest neighbors, M4 = M2 + upwind.

The upwind formula is fixed in src/forecasting/upwind.py. This script does not
search weights. 2016-12-20 is a safety check, not a fitting target.
Does not modify the model lock.

Example:
    py -3 scripts/ablation_upwind_offline.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from src.eda.db import read_sql  # noqa: E402
from src.forecasting.constants import (  # noqa: E402
    FEATURE_COLS_V2,
    SAMPLE_WEIGHT_HIGH,
    SAMPLE_WEIGHT_THRESHOLD,
    TARGET_COL,
    TEST_END,
    TEST_START,
    TRAIN_END,
    VAL_END,
    VAL_START,
)
from src.forecasting.metrics import regression_metrics  # noqa: E402
from src.forecasting.models import RANDOM_STATE, compute_sample_weights, run_histgb  # noqa: E402
from src.forecasting.spatial_calendar import (  # noqa: E402
    SPATIAL_FEATURES,
    add_spatial_features,
)
from src.forecasting.upwind import UPWIND_FEATURES, UPWIND_WEAK_WIND_M_S, add_upwind_features  # noqa: E402

OUT = ROOT / "artifacts" / "forecasting" / "upwind_poc"
MATRIX_PARQUET = ROOT / "artifacts" / "forecasting" / "feature_matrix_v2.parquet"
STATION_MAP = ROOT / "data" / "clustering" / "station_cluster_assignment.csv"
STATIONS = ROOT / "data" / "raw" / "reference" / "stations.csv"
WIND_CACHE = OUT / "wind_panel.parquet"

# Fixed before fitting M4. Dec 20 is not used to choose the formula.
PROMOTE_CRITERIA = {
    "rule": (
        "M4_CANDIDATE only if M4 beats M0 on the existing gate "
        "(val and test dMAE <= -0.15, winter and high-PM not worse by >0.10, "
        ">=7/12 stations), is not worse than M2 by >0.05 on val or test, "
        "winter and high-PM vs M2 not worse by >0.10, rapid-rise test vs M2 "
        "not worse by >0.10, and the Gucheng 2016-12-20 >=500 window is not "
        "severely worse than M0 (dMAE <= +10). Otherwise KEEP_M2. "
        "The lock is not updated either way."
    ),
    "delta_mae_improve_threshold": -0.15,
    "no_harm_threshold": 0.10,
    "m2_regression_tolerance": 0.05,
    "min_stations_improved_on_test": 7,
    "high_pm_threshold": 115.0,
    "rapid_rise_ug_m3": 20.0,
    "tail_severe_delta_mae": 10.0,
    "tail_definition": "Gucheng target hours on 2016-12-20 with actual PM2.5 >= 500",
    "weak_wind_m_s": UPWIND_WEAK_WIND_M_S,
}

MODELS = ("m0", "m2", "m4")
SUBURBAN = ("Huairou", "Gucheng", "Shunyi")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _finite(x: Any) -> float | None:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if np.isnan(f) or np.isinf(f):
        return None
    return f


def _load_wind() -> pd.DataFrame:
    if WIND_CACHE.is_file():
        wind = pd.read_parquet(WIND_CACHE)
        wind["event_time_local"] = pd.to_datetime(wind["event_time_local"])
        return wind
    wind = read_sql(
        """
        select s.station_name,
               f.event_time_local,
               w.azimuth_deg,
               w.wind_direction
        from dwh.fact_air_quality_hourly f
        join dwh.dim_station s on f.station_key = s.station_key
        join dwh.dim_wind_direction w on f.wind_direction_key = w.wind_direction_key
        where f.event_time_local >= '2013-03-01 00:00:00'
          and f.event_time_local <= '2016-12-31 23:00:00'
        """
    )
    wind["event_time_local"] = pd.to_datetime(wind["event_time_local"])
    wind["azimuth_deg"] = pd.to_numeric(wind["azimuth_deg"], errors="coerce")
    OUT.mkdir(parents=True, exist_ok=True)
    wind.to_parquet(WIND_CACHE, index=False)
    return wind


def _load_frame(wind: pd.DataFrame) -> pd.DataFrame:
    df = pd.read_parquet(MATRIX_PARQUET)
    df["event_time_local"] = pd.to_datetime(df["event_time_local"])
    df["station_key"] = df["station_key"].astype(int)
    names = pd.read_csv(STATION_MAP)[["station_key", "station_name"]]
    names["station_key"] = names["station_key"].astype(int)
    df = df.merge(names, on="station_key", how="left")
    if df["station_name"].isna().any():
        raise KeyError("station_key missing from cluster assignment")
    stations = pd.read_csv(STATIONS)
    df, _ = add_spatial_features(df, stations)
    df = add_upwind_features(df, stations, wind)
    return df


def _block(eval_df: pd.DataFrame, mask: pd.Series) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for split in ("train", "val", "test"):
        sub = eval_df[mask & eval_df["split"].eq(split)]
        cell: dict[str, Any] = {"n": int(len(sub))}
        if sub.empty:
            for name in MODELS:
                cell[name] = None
            cell["delta_vs_m0"] = {name: None for name in MODELS if name != "m0"}
            cell["delta_vs_m2"] = {"m4": None}
            out[split] = cell
            continue
        for name in MODELS:
            metrics = regression_metrics(sub[TARGET_COL], sub[f"y_hat_{name}"])
            metrics["mean_signed_error"] = float(sub[f"signed_{name}"].mean())
            cell[name] = metrics
        cell["delta_vs_m0"] = {
            name: _finite(cell[name]["mae"] - cell["m0"]["mae"]) for name in MODELS if name != "m0"
        }
        cell["delta_vs_m2"] = {"m4": _finite(cell["m4"]["mae"] - cell["m2"]["mae"])}
        out[split] = cell
    return out


def _station_episodes(frame: pd.DataFrame) -> pd.DataFrame:
    """Consecutive target hours with actual PM2.5 >= 500, per station. Post hoc."""
    rows = []
    eid = 0
    ordered = frame.sort_values(["station_name", "target_time_local"])
    for station, block in ordered.groupby("station_name", sort=False):
        times = pd.to_datetime(block["target_time_local"]).to_numpy()
        start = 0
        for i in range(len(block) + 1):
            gap = i > start and i < len(block) and (times[i] - times[i - 1]) != np.timedelta64(1, "h")
            if i == len(block) or gap:
                part = block.iloc[start:i]
                if len(part) >= 1:
                    row = {
                        "episode": eid,
                        "station_name": station,
                        "start": str(part["target_time_local"].min()),
                        "end": str(part["target_time_local"].max()),
                        "n": int(len(part)),
                        "split": str(part["split"].iloc[0]),
                    }
                    for name in MODELS:
                        row[f"mae_{name}"] = float(part[f"abs_err_{name}"].mean())
                    row["delta_m4_m0"] = row["mae_m4"] - row["mae_m0"]
                    row["delta_m4_m2"] = row["mae_m4"] - row["mae_m2"]
                    row["delta_m2_m0"] = row["mae_m2"] - row["mae_m0"]
                    rows.append(row)
                    eid += 1
                start = i
    return pd.DataFrame(rows)


def _decide(metrics: dict[str, Any], n_improved: int, tail_delta: float | None) -> dict[str, Any]:
    crit = PROMOTE_CRITERIA
    d_m0 = {
        "val": metrics["overall"]["val"]["delta_vs_m0"]["m4"],
        "test": metrics["overall"]["test"]["delta_vs_m0"]["m4"],
        "winter": metrics["winter"]["test"]["delta_vs_m0"]["m4"],
        "high_pm": metrics["high_pm"]["test"]["delta_vs_m0"]["m4"],
    }
    d_m2 = {
        "val": metrics["overall"]["val"]["delta_vs_m2"]["m4"],
        "test": metrics["overall"]["test"]["delta_vs_m2"]["m4"],
        "winter": metrics["winter"]["test"]["delta_vs_m2"]["m4"],
        "high_pm": metrics["high_pm"]["test"]["delta_vs_m2"]["m4"],
        "rapid": metrics["rapid_rise"]["test"]["delta_vs_m2"]["m4"],
    }
    beats_m0 = (
        d_m0["val"] is not None
        and d_m0["test"] is not None
        and d_m0["val"] <= crit["delta_mae_improve_threshold"]
        and d_m0["test"] <= crit["delta_mae_improve_threshold"]
        and d_m0["winter"] is not None
        and d_m0["high_pm"] is not None
        and d_m0["winter"] <= crit["no_harm_threshold"]
        and d_m0["high_pm"] <= crit["no_harm_threshold"]
        and n_improved >= crit["min_stations_improved_on_test"]
    )
    holds_m2 = (
        d_m2["val"] is not None
        and d_m2["test"] is not None
        and d_m2["val"] <= crit["m2_regression_tolerance"]
        and d_m2["test"] <= crit["m2_regression_tolerance"]
        and d_m2["winter"] is not None
        and d_m2["high_pm"] is not None
        and d_m2["rapid"] is not None
        and d_m2["winter"] <= crit["no_harm_threshold"]
        and d_m2["high_pm"] <= crit["no_harm_threshold"]
        and d_m2["rapid"] <= crit["no_harm_threshold"]
    )
    tail_ok = tail_delta is not None and tail_delta <= crit["tail_severe_delta_mae"]
    if beats_m0 and holds_m2 and tail_ok:
        decision = "M4_CANDIDATE"
        note = "Upwind clears M0, does not give back the M2 gain, and does not repeat the severe Gucheng tail. Lock still unchanged."
    else:
        decision = "KEEP_M2"
        note = "Upwind does not replace M2. The HistGB v2 lock stays. Spatial M2 remains the promote candidate."
    return {
        "decision": decision,
        "note": note,
        "beats_m0_gate": beats_m0,
        "holds_m2": holds_m2,
        "tail_ok": tail_ok,
        "delta_vs_m0": d_m0,
        "delta_vs_m2": d_m2,
        "tail_delta_mae_m4_minus_m0": tail_delta,
        "stations_improved_vs_m0": n_improved,
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    started = _utc_now()
    wind = _load_wind()
    frame = _load_frame(wind)
    train = frame[frame["split"].eq("train")].copy()
    weights = compute_sample_weights(train["pm25_ug_m3"], train[TARGET_COL])
    feature_sets = {
        "m0": list(FEATURE_COLS_V2),
        "m2": [*FEATURE_COLS_V2, *SPATIAL_FEATURES],
        "m4": [*FEATURE_COLS_V2, *SPATIAL_FEATURES, *UPWIND_FEATURES],
    }
    preds: dict[str, np.ndarray] = {}
    for name, cols in feature_sets.items():
        print(f"Training {name} on {len(train)} rows, {len(cols)} features ...", flush=True)
        result = run_histgb(train, frame, feature_cols=cols, sample_weight=weights)
        preds[name] = result.predictions.to_numpy()

    eval_df = frame[
        [
            "station_key",
            "station_name",
            "event_time_local",
            "target_time_local",
            "split",
            "season",
            "pm25_ug_m3",
            TARGET_COL,
            "cluster_label",
            *UPWIND_FEATURES,
        ]
    ].copy()
    for name in MODELS:
        eval_df[f"y_hat_{name}"] = preds[name]
        eval_df[f"abs_err_{name}"] = (eval_df[TARGET_COL] - eval_df[f"y_hat_{name}"]).abs()
        eval_df[f"signed_{name}"] = eval_df[f"y_hat_{name}"] - eval_df[TARGET_COL]
    eval_df["winter"] = eval_df["season"].astype(str).str.lower().eq("winter")
    eval_df["rapid_rise"] = (eval_df[TARGET_COL] - eval_df["pm25_ug_m3"]) >= PROMOTE_CRITERIA["rapid_rise_ug_m3"]
    target = pd.to_datetime(eval_df["target_time_local"])
    tail_mask = (
        eval_df["station_name"].eq("Gucheng")
        & target.between("2016-12-20 00:00:00", "2016-12-20 23:00:00")
        & (eval_df[TARGET_COL] >= 500)
    )
    masks = {
        "overall": pd.Series(True, index=eval_df.index),
        "winter": eval_df["winter"],
        "high_pm": eval_df[TARGET_COL] >= PROMOTE_CRITERIA["high_pm_threshold"],
        "rapid_rise": eval_df["rapid_rise"],
        "ge500": eval_df[TARGET_COL] >= 500,
        "gucheng_20161220_ge500": tail_mask,
    }
    metrics = {name: _block(eval_df, mask) for name, mask in masks.items()}

    test = eval_df[eval_df["split"].eq("test")]
    station_rows = []
    for station, sub in test.groupby("station_name", sort=True):
        row: dict[str, Any] = {"station_name": station, "n": int(len(sub))}
        m0 = float(sub["abs_err_m0"].mean())
        m2 = float(sub["abs_err_m2"].mean())
        m4 = float(sub["abs_err_m4"].mean())
        row.update({"mae_m0": m0, "mae_m2": m2, "mae_m4": m4, "delta_m4_m0": m4 - m0, "delta_m4_m2": m4 - m2})
        winter_sub = sub[sub["winter"]]
        row["n_winter"] = int(len(winter_sub))
        if len(winter_sub):
            row["delta_m4_m0_winter"] = float(winter_sub["abs_err_m4"].mean() - winter_sub["abs_err_m0"].mean())
            row["delta_m4_m2_winter"] = float(winter_sub["abs_err_m4"].mean() - winter_sub["abs_err_m2"].mean())
        station_rows.append(row)
    stations_df = pd.DataFrame(station_rows)
    n_improved = int((stations_df["delta_m4_m0"] < 0).sum())

    tail = metrics["gucheng_20161220_ge500"]["test"]
    tail_delta = None if tail["m4"] is None else tail["delta_vs_m0"]["m4"]
    decision = _decide(metrics, n_improved, tail_delta)

    ge500_test = eval_df[eval_df["split"].eq("test") & (eval_df[TARGET_COL] >= 500)]
    episodes = _station_episodes(ge500_test)
    episodes_path = OUT / "extreme_ge500_episodes_test.csv"
    episodes.to_csv(episodes_path, index=False)
    long_eps = episodes[episodes["n"] >= 3] if len(episodes) else episodes
    episode_summary = {
        "n_episodes": int(len(episodes)),
        "n_episodes_len_ge3": int(len(long_eps)),
        "n_m4_better_than_m0": int((episodes["delta_m4_m0"] < 0).sum()) if len(episodes) else 0,
        "n_m4_better_than_m2": int((episodes["delta_m4_m2"] < 0).sum()) if len(episodes) else 0,
        "n_long_m4_better_than_m2": int((long_eps["delta_m4_m2"] < 0).sum()) if len(long_eps) else 0,
    }

    suburban = stations_df[stations_df["station_name"].isin(SUBURBAN)].to_dict(orient="records")
    nulls = {col: int(frame[col].isna().sum()) for col in ("upwind_pm25", "upwind_pm25_lag1", "upwind_minus_local")}
    weak_rate = float(frame["upwind_weak_wind"].mean())
    unavail_rate = float(frame["upwind_unavailable"].mean())

    # Response ratio on test rapid rises.
    rapid = eval_df[eval_df["split"].eq("test") & eval_df["rapid_rise"]]
    actual_delta = float((rapid[TARGET_COL] - rapid["pm25_ug_m3"]).mean())
    response = {
        name: _finite(float((rapid[f"y_hat_{name}"] - rapid["pm25_ug_m3"]).mean()) / actual_delta)
        for name in MODELS
    }

    report = {
        "ok": True,
        "phase": "upwind_poc_one_shot",
        "started_at": started,
        "finished_at": _utc_now(),
        "model_lock_untouched": True,
        "formula": {
            "wind_convention": "meteorological degrees, 0 = wind from north",
            "weights": "max(0, cos(bearing - wind_from)) / distance_km over all other stations",
            "lags": "PM and wind at t, and at t-1h; never t+1",
            "weak_wind_m_s": UPWIND_WEAK_WIND_M_S,
            "features": list(UPWIND_FEATURES),
            "keeps_m2_features": True,
        },
        "promote_criteria_preregistered": PROMOTE_CRITERIA,
        "locked_reference": {
            "random_state": RANDOM_STATE,
            "sample_weight": {"threshold": SAMPLE_WEIGHT_THRESHOLD, "high_weight": SAMPLE_WEIGHT_HIGH},
            "split": {"train_end": TRAIN_END, "val": [VAL_START, VAL_END], "test": [TEST_START, TEST_END]},
            "feature_counts": {k: len(v) for k, v in feature_sets.items()},
        },
        "data": {
            "n_rows": int(len(frame)),
            "n_train": int(len(train)),
            "upwind_nulls": nulls,
            "upwind_weak_rate": weak_rate,
            "upwind_unavailable_rate": unavail_rate,
        },
        "metrics": metrics,
        "stations_improved_vs_m0": n_improved,
        "suburban_test": suburban,
        "episode_summary_test_ge500": episode_summary,
        "rapid_rise_response_ratio_test": response,
        "decision": decision,
    }
    stations_df.to_csv(OUT / "delta_mae_by_station_test.csv", index=False)
    pred_keep = [
        "station_name",
        "event_time_local",
        "target_time_local",
        "split",
        "pm25_ug_m3",
        TARGET_COL,
        "y_hat_m0",
        "y_hat_m2",
        "y_hat_m4",
        "signed_m0",
        "signed_m2",
        "signed_m4",
        "abs_err_m0",
        "abs_err_m2",
        "abs_err_m4",
    ]
    eval_df.loc[:, pred_keep].to_parquet(OUT / "predictions_m0_m2_m4.parquet", index=False)
    report_path = OUT / "ablation_report.json"
    report_path.write_text(json.dumps(report, indent=2, allow_nan=True) + "\n", encoding="utf-8")
    summary = {
        "decision": decision["decision"],
        "tail_ok": decision["tail_ok"],
        "tail_delta_m4_m0": tail_delta,
        "delta_vs_m0_test": decision["delta_vs_m0"]["test"],
        "delta_vs_m0_winter": decision["delta_vs_m0"]["winter"],
        "delta_vs_m2_test": decision["delta_vs_m2"]["test"],
        "delta_vs_m2_winter": decision["delta_vs_m2"]["winter"],
        "delta_vs_m2_high_pm": decision["delta_vs_m2"]["high_pm"],
        "delta_vs_m2_rapid": decision["delta_vs_m2"]["rapid"],
        "response_ratio": response,
        "episodes": episode_summary,
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
