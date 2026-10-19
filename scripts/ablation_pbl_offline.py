#!/usr/bin/env python3
"""One-shot offline ablation: HistGB v2 baseline (M0) vs +PBL_lag_1 (M1).

Does NOT touch model lock, warehouse, or Open-Meteo ingest pipeline.
Uses locked v2 hyperparameters / sample weights / temporal split.

Example:
    py -3 scripts/ablation_pbl_offline.py
"""

from __future__ import annotations

import argparse
import json
import sys
import time
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
from src.forecasting.models import (  # noqa: E402
    RANDOM_STATE,
    compute_sample_weights,
    run_histgb,
)
from src.ingestion.openmeteo_client import (  # noqa: E402
    fetch_historical_weather,
    hourly_to_records,
)
from src.ingestion.openmeteo_to_minio import iter_date_chunks  # noqa: E402
from src.reference.stations import load_stations  # noqa: E402

OUT = ROOT / "artifacts" / "forecasting" / "pbl_ablation"
MATRIX_PARQUET = ROOT / "artifacts" / "forecasting" / "feature_matrix_v2.parquet"
PBL_CACHE = OUT / "pbl_panel_cache.parquet"

# Pre-registered promote gate (fixed before looking at results).
PROMOTE_CRITERIA = {
    "rule": (
        "PROMOTE only if val AND test ΔMAE(M1−M0) ≤ −0.15 µg/m³, "
        "winter-test and highPM-test do not worsen by >0.10, "
        "and ≥7/12 stations improve on test. "
        "WINTER_ONLY if winter-test ΔMAE ≤ −0.15 but overall promote fails. "
        "Otherwise CLOSE_BRANCH."
    ),
    "delta_mae_improve_threshold": -0.15,
    "no_harm_threshold": 0.10,
    "min_stations_improved_on_test": 7,
    "high_pm_threshold": 115.0,
}

# Fetch a day before ML window so lag-1 exists at first train hour.
PBL_FETCH_START = "2013-02-28"
PBL_FETCH_END = "2016-12-31"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _finite(x: Any) -> float | None:
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if np.isnan(f) or np.isinf(f):
        return None
    return f


def _load_matrix() -> pd.DataFrame:
    if not MATRIX_PARQUET.exists():
        raise FileNotFoundError(
            f"Missing {MATRIX_PARQUET} — run scripts/run_forecasting_v2a.py first."
        )
    df = pd.read_parquet(MATRIX_PARQUET)
    df["event_time_local"] = pd.to_datetime(df["event_time_local"])
    return df


def _station_key_map() -> dict[int, str]:
    dim = read_sql("select station_key, station_name from dwh.dim_station")
    return {int(r.station_key): str(r.station_name) for r in dim.itertuples(index=False)}


def _fetch_pbl_panel(*, force_refresh: bool = False) -> pd.DataFrame:
    if PBL_CACHE.exists() and not force_refresh:
        panel = pd.read_parquet(PBL_CACHE)
        panel["event_time_local"] = pd.to_datetime(panel["event_time_local"])
        print(f"Loaded PBL cache {PBL_CACHE} ({len(panel)} rows)")
        return panel

    OUT.mkdir(parents=True, exist_ok=True)
    stations = load_stations()
    key_map = _station_key_map()
    name_to_key = {v: k for k, v in key_map.items()}
    rows: list[pd.DataFrame] = []

    for i, (name, ref) in enumerate(sorted(stations.items()), start=1):
        if name not in name_to_key:
            raise KeyError(f"Station {name} missing from dim_station")
        station_key = name_to_key[name]
        print(f"[{i}/{len(stations)}] Fetch PBL {name} ...")
        for chunk_start, chunk_end in iter_date_chunks(PBL_FETCH_START, PBL_FETCH_END):
            result = fetch_historical_weather(
                station=name,
                latitude=ref.latitude,
                longitude=ref.longitude,
                start_date=chunk_start,
                end_date=chunk_end,
                hourly=("boundary_layer_height",),
            )
            chunk = pd.DataFrame(hourly_to_records(result.payload))
            if chunk.empty:
                continue
            chunk["event_time_local"] = pd.to_datetime(chunk["time"])
            chunk["station_name"] = name
            chunk["station_key"] = station_key
            chunk["boundary_layer_height_m"] = chunk["boundary_layer_height"].astype(float)
            rows.append(chunk[["station_key", "station_name", "event_time_local", "boundary_layer_height_m"]])
            time.sleep(0.15)  # be polite to archive API

    if not rows:
        raise RuntimeError("No PBL rows fetched")
    panel = pd.concat(rows, ignore_index=True)
    panel = panel.drop_duplicates(subset=["station_key", "event_time_local"], keep="last")
    panel = panel.sort_values(["station_key", "event_time_local"]).reset_index(drop=True)
    panel.to_parquet(PBL_CACHE, index=False)
    print(f"Wrote PBL cache {PBL_CACHE} ({len(panel)} rows)")
    return panel


def _attach_pbl_lag1(matrix: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    """Join PBL at hour t, then lag-1 within station (available at origin t)."""
    df = matrix.copy()
    key_map = _station_key_map()
    df["station_name"] = df["station_key"].map(key_map)

    pbl = panel[["station_key", "event_time_local", "boundary_layer_height_m"]].copy()
    merged = df.merge(pbl, on=["station_key", "event_time_local"], how="left")
    merged = merged.sort_values(["station_key", "event_time_local"])
    # Lag within station: PBL(t-1) for row at origin t — no future info.
    merged["pbl_lag_1"] = merged.groupby("station_key", sort=False)[
        "boundary_layer_height_m"
    ].shift(1)
    return merged


def _slice_metrics(y: pd.Series, pred: pd.Series) -> dict[str, float]:
    return regression_metrics(y, pred)


def _group_mae(frame: pd.DataFrame, pred_col: str, group_col: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for key, sub in frame.groupby(group_col, sort=True):
        out[str(key)] = float(np.mean(np.abs(sub[TARGET_COL] - sub[pred_col])))
    return out


def _decide(report_metrics: dict[str, Any]) -> dict[str, Any]:
    thr = PROMOTE_CRITERIA["delta_mae_improve_threshold"]
    harm = PROMOTE_CRITERIA["no_harm_threshold"]
    min_st = PROMOTE_CRITERIA["min_stations_improved_on_test"]

    d_val = report_metrics["overall"]["val"]["delta_mae"]
    d_test = report_metrics["overall"]["test"]["delta_mae"]
    d_winter_test = report_metrics["winter"]["test"]["delta_mae"]
    d_high_test = report_metrics["high_pm"]["test"]["delta_mae"]
    n_improved = report_metrics["stations_test"]["n_improved"]

    promote_ok = (
        d_val is not None
        and d_test is not None
        and d_val <= thr
        and d_test <= thr
        and d_winter_test is not None
        and d_high_test is not None
        and d_winter_test <= harm
        and d_high_test <= harm
        and n_improved >= min_st
    )
    winter_only = (
        not promote_ok
        and d_winter_test is not None
        and d_winter_test <= thr
    )

    if promote_ok:
        decision = "PROMOTE_CANDIDATE"
        note = "Stable val+test improvement under pre-registered gate — only then consider ingest cost."
    elif winter_only:
        decision = "WINTER_ONLY"
        note = (
            "Winter-test improves enough, but overall promote gate failed. "
            "Record as seasonal research note; do not promote full pipeline."
        )
    else:
        decision = "CLOSE_BRANCH"
        note = (
            "No clear stable incremental value vs locked HistGB v2 baseline. "
            "Keep POC/ablation artifacts for the report; do not ingest PBL."
        )

    return {
        "decision": decision,
        "note": note,
        "checked": {
            "delta_mae_val": d_val,
            "delta_mae_test": d_test,
            "delta_mae_winter_test": d_winter_test,
            "delta_mae_high_pm_test": d_high_test,
            "stations_improved_test": n_improved,
        },
        "criteria": PROMOTE_CRITERIA,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline PBL lag-1 ablation (one-shot)")
    parser.add_argument("--force-refresh-pbl", action="store_true")
    parser.add_argument(
        "--stations",
        default="all",
        help="Comma-separated station names, or 'all' (default 12)",
    )
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    started = _utc_now()

    matrix = _load_matrix()
    panel = _fetch_pbl_panel(force_refresh=args.force_refresh_pbl)

    if args.stations != "all":
        keep = {s.strip() for s in args.stations.split(",") if s.strip()}
        key_map = _station_key_map()
        keep_keys = {k for k, n in key_map.items() if n in keep}
        matrix = matrix[matrix["station_key"].isin(keep_keys)].copy()
        panel = panel[panel["station_name"].isin(keep)].copy()

    merged = _attach_pbl_lag1(matrix, panel)
    n_before = len(merged)
    usable = merged[merged["pbl_lag_1"].notna() & merged[TARGET_COL].notna()].copy()
    n_after = len(usable)

    # Same row set for M0 and M1.
    train = usable[usable["split"] == "train"].copy()
    if train.empty:
        raise RuntimeError("Empty train after PBL join filter")

    feats_m0 = list(FEATURE_COLS_V2)
    feats_m1 = [*FEATURE_COLS_V2, "pbl_lag_1"]

    weights = compute_sample_weights(
        train["pm25_ug_m3"],
        train[TARGET_COL],
        threshold=SAMPLE_WEIGHT_THRESHOLD,
        high_weight=SAMPLE_WEIGHT_HIGH,
    )

    print(f"Training M0 HistGB on {len(train)} rows / {n_after} eval rows ...")
    m0 = run_histgb(train, usable, feature_cols=feats_m0, sample_weight=weights)
    print("Training M1 HistGB (+pbl_lag_1) ...")
    m1 = run_histgb(train, usable, feature_cols=feats_m1, sample_weight=weights)

    eval_df = usable[
        [
            "station_key",
            "station_name",
            "event_time_local",
            "split",
            "season",
            "pm25_ug_m3",
            TARGET_COL,
            "cluster_label",
            "pbl_lag_1",
        ]
    ].copy()
    eval_df["y_hat_m0"] = m0.predictions.to_numpy()
    eval_df["y_hat_m1"] = m1.predictions.to_numpy()
    eval_df["abs_err_m0"] = (eval_df[TARGET_COL] - eval_df["y_hat_m0"]).abs()
    eval_df["abs_err_m1"] = (eval_df[TARGET_COL] - eval_df["y_hat_m1"]).abs()

    high_pm = PROMOTE_CRITERIA["high_pm_threshold"]

    def block(mask: pd.Series) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for split in ("train", "val", "test"):
            sub = eval_df[mask & (eval_df["split"] == split)]
            if sub.empty:
                out[split] = {
                    "n": 0,
                    "m0": None,
                    "m1": None,
                    "delta_mae": None,
                    "delta_rmse": None,
                }
                continue
            m0m = _slice_metrics(sub[TARGET_COL], sub["y_hat_m0"])
            m1m = _slice_metrics(sub[TARGET_COL], sub["y_hat_m1"])
            out[split] = {
                "n": int(len(sub)),
                "m0": m0m,
                "m1": m1m,
                "delta_mae": _finite(m1m["mae"] - m0m["mae"]),
                "delta_rmse": _finite(m1m["rmse"] - m0m["rmse"]),
            }
        return out

    winter_mask = eval_df["season"].astype(str).str.lower().eq("winter")
    high_mask = eval_df[TARGET_COL] >= high_pm

    metrics = {
        "overall": block(pd.Series(True, index=eval_df.index)),
        "winter": block(winter_mask),
        "high_pm": block(high_mask),
    }

    # Per-station ΔMAE on test
    test = eval_df[eval_df["split"] == "test"]
    station_rows = []
    for station, sub in test.groupby("station_name", sort=True):
        m0_mae = float(sub["abs_err_m0"].mean())
        m1_mae = float(sub["abs_err_m1"].mean())
        station_rows.append(
            {
                "station_name": station,
                "cluster_label": str(sub["cluster_label"].iloc[0]),
                "n": int(len(sub)),
                "mae_m0": m0_mae,
                "mae_m1": m1_mae,
                "delta_mae": m1_mae - m0_mae,
            }
        )
    stations_df = pd.DataFrame(station_rows)
    n_improved = int((stations_df["delta_mae"] < 0).sum()) if len(stations_df) else 0
    metrics["stations_test"] = {
        "rows": station_rows,
        "n_improved": n_improved,
        "n_stations": int(len(stations_df)),
        "mean_delta_mae": _finite(float(stations_df["delta_mae"].mean()))
        if len(stations_df)
        else None,
    }

    # Per-split summary table (overall)
    split_delta = {
        split: metrics["overall"][split]["delta_mae"] for split in ("train", "val", "test")
    }

    decision = _decide(metrics)

    # Leakage checklist baked into report
    leakage = {
        "feature": "pbl_lag_1",
        "definition": "boundary_layer_height at event_time_local − 1h, within station",
        "uses_pbl_at_t": False,
        "uses_pbl_at_tplus1": False,
        "same_row_set_m0_m1": True,
        "rows_dropped_for_null_pbl_lag1": int(n_before - n_after),
        "note": (
            "Rows with null pbl_lag_1 dropped from BOTH models so comparison uses "
            "identical record sets. HistGB hyperparams/sample weights match v2 lock."
        ),
    }

    report = {
        "ok": True,
        "phase": "PBL_offline_ablation_one_shot",
        "started_at": started,
        "finished_at": _utc_now(),
        "locked_reference": {
            "algorithm": "hist_gradient_boosting",
            "random_state": RANDOM_STATE,
            "feature_cols_m0": feats_m0,
            "feature_cols_m1": feats_m1,
            "sample_weight": {
                "threshold": SAMPLE_WEIGHT_THRESHOLD,
                "high_weight": SAMPLE_WEIGHT_HIGH,
            },
            "split": {
                "train_end": TRAIN_END,
                "val": [VAL_START, VAL_END],
                "test": [TEST_START, TEST_END],
            },
            "model_lock_untouched": True,
        },
        "data": {
            "matrix": str(MATRIX_PARQUET.relative_to(ROOT)).replace("\\", "/"),
            "pbl_cache": str(PBL_CACHE.relative_to(ROOT)).replace("\\", "/"),
            "n_matrix": n_before,
            "n_comparable": n_after,
            "n_train": int(len(train)),
            "stations": sorted(usable["station_name"].dropna().unique().tolist()),
            "n_stations": int(usable["station_key"].nunique()),
        },
        "leakage": leakage,
        "promote_criteria_preregistered": PROMOTE_CRITERIA,
        "metrics": metrics,
        "delta_mae_by_split": split_delta,
        "decision": decision,
    }

    pred_path = OUT / "predictions_m0_m1.parquet"
    eval_df.to_parquet(pred_path, index=False)
    stations_path = OUT / "delta_mae_by_station_test.csv"
    stations_df.to_csv(stations_path, index=False)
    report_path = OUT / "ablation_report.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    summary = {
        "decision": decision["decision"],
        "note": decision["note"],
        "delta_mae_by_split": split_delta,
        "winter_test_delta_mae": metrics["winter"]["test"]["delta_mae"],
        "high_pm_test_delta_mae": metrics["high_pm"]["test"]["delta_mae"],
        "stations_improved_test": f"{n_improved}/{len(stations_df)}",
        "report": str(report_path.relative_to(ROOT)).replace("\\", "/"),
        "predictions": str(pred_path.relative_to(ROOT)).replace("\\", "/"),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
