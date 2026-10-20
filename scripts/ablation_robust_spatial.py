#!/usr/bin/env python3
"""Closed M5 POC: M2 with median neighbor aggregation instead of IDW.

Decision is KEEP_M2. Do not refit, and do not add another aggregator on this test set.
See artifacts/forecasting/robust_spatial_poc/decision_note.md.

M5 replaces the four IDW-derived spatial columns and nothing else. The suspect
flag is joined after the forecasts and is not a feature. 2016-12-20 is excluded
from the promote evidence. Does not modify the model lock, UCI files, or the
feature matrix.

Example:
    py -3 scripts/ablation_robust_spatial.py
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
    SPATIAL_MEDIAN_FEATURES,
    add_spatial_features,
    nearest_neighbor_table,
    statutory_heating_mask,
)
from src.forecasting.spatial_quality import score_spatial_quality  # noqa: E402

OUT = ROOT / "artifacts" / "forecasting" / "robust_spatial_poc"
MATRIX_PARQUET = ROOT / "artifacts" / "forecasting" / "feature_matrix_v2.parquet"
STATION_MAP = ROOT / "data" / "clustering" / "station_cluster_assignment.csv"
STATIONS = ROOT / "data" / "raw" / "reference" / "stations.csv"
INVENTORY = ROOT / "data" / "raw" / "reference" / "file_inventory.csv"

# Locked reproduction targets from the spatial ablation (same rows, same HistGB).
REF_M0_TEST_MAE = 8.871842776028974
REF_M2_TEST_MAE = 8.573582186189157
REF_M0_WINTER_TEST_MAE = 14.080199969436988
REF_M2_WINTER_TEST_MAE = 13.680496172924935
REPRO_TOLERANCE = 0.02

# Fixed before fitting M5. The diagnostic day is not a fitting target.
DIAGNOSTIC_DAY = date(2016, 12, 20)
LARGE_GAP_UG = 50.0
EXTREME_UG = 500.0
PROMOTE_CRITERIA = {
    "rule": (
        "PROMOTE_CANDIDATE only if M5 passes the existing M0 gate "
        "(val and test dMAE <= -0.15, winter-test and high-PM test not worse "
        "by >0.10, >=7/12 stations), the suspect-neighbor slice improves by "
        "at least 1 µg/m³ on val and on test with that diagnostic day removed, "
        "each of those slices has at least 30 origin hours, unflagged hours "
        "are not worse than M2 by >0.10, unflagged large local-neighbor gaps "
        "are not worse than M2 by >0.50, test >=500 is not worse than M2 by "
        ">1 or than M0 by >10, and M5 wins at least as many test >=500 "
        "station-episodes and city events as it loses to M2. "
        "ROBUSTNESS_ONLY if the suspect slice improves on val and test, "
        "unflagged hours stay within 0.10 of M2, and the tail vs M2 stays "
        "within 5, but the promote gate fails. Otherwise KEEP_M2. "
        "The lock is not updated either way."
    ),
    "delta_mae_improve_threshold": -0.15,
    "no_harm_threshold": 0.10,
    "min_stations_improved_on_test": 7,
    "high_pm_threshold": 115.0,
    "rapid_change_ug_m3": 20.0,
    "suspect_improve_ug": -1.0,
    "min_suspect_hours": 30,
    "normal_harm_ug": 0.10,
    "heterogeneity_harm_ug": 0.50,
    "tail_vs_m2_ug": 1.0,
    "tail_vs_m2_research_ug": 5.0,
    "tail_vs_m0_severe_ug": 10.0,
    "large_gap_ug": LARGE_GAP_UG,
    "extreme_ug": EXTREME_UG,
    "diagnostic_day": str(DIAGNOSTIC_DAY),
}

MODELS = ("m0", "m2", "m5")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if np.isnan(number) or np.isinf(number):
        return None
    return number


def _load_uci_pm25() -> pd.DataFrame:
    inventory = pd.read_csv(INVENTORY)
    frames = []
    for row in inventory.itertuples(index=False):
        raw = pd.read_csv(
            ROOT / row.relative_path,
            usecols=["year", "month", "day", "hour", "PM2.5", "station"],
        )
        raw["event_time_local"] = pd.to_datetime(raw[["year", "month", "day", "hour"]])
        raw = raw.rename(columns={"PM2.5": "pm25_ug_m3", "station": "station_name"})
        frames.append(raw[["station_name", "event_time_local", "pm25_ug_m3"]])
    panel = pd.concat(frames, ignore_index=True)
    if panel.duplicated(["station_name", "event_time_local"]).any():
        raise ValueError("UCI panel has duplicate station hours")
    return panel


def _load_frame() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not MATRIX_PARQUET.exists():
        raise FileNotFoundError(f"Missing {MATRIX_PARQUET}")
    frame = pd.read_parquet(MATRIX_PARQUET)
    frame["event_time_local"] = pd.to_datetime(frame["event_time_local"])
    frame["target_time_local"] = pd.to_datetime(frame["target_time_local"])
    frame["station_key"] = frame["station_key"].astype(int)
    names = pd.read_csv(STATION_MAP)[["station_key", "station_name"]]
    names["station_key"] = names["station_key"].astype(int)
    frame = frame.merge(names, on="station_key", how="left")
    if frame["station_name"].isna().any():
        raise KeyError("station_key missing from cluster assignment")
    stations = pd.read_csv(STATIONS)
    frame, neighbors = add_spatial_features(frame, stations, include_median=True)
    return frame, neighbors


def _attach_suspect(frame: pd.DataFrame, neighbors: pd.DataFrame, uci: pd.DataFrame) -> pd.DataFrame:
    """Mark origin hours whose spatial inputs include a review-flagged neighbor.

    The flag uses t+1 of the neighbor hour being reviewed. It is attached after
    the features exist and is not passed to the model.
    """
    scored = score_spatial_quality(uci, pd.read_csv(STATIONS))
    wide = (
        scored.pivot(index="event_time_local", columns="station_name", values="suspect_spatiotemporal")
        .astype("boolean")
        .fillna(False)
        .astype(bool)
    )
    out = frame.copy()
    any_flag = np.zeros(len(out), dtype=bool)
    at_t = np.zeros(len(out), dtype=bool)
    name_map = {
        station: group.sort_values("neighbor_rank")["neighbor_name"].astype(str).tolist()
        for station, group in neighbors.groupby("station_name", sort=False)
    }
    for station, index in out.groupby("station_name", sort=False).groups.items():
        names = [name for name in name_map.get(str(station), []) if name in wide.columns]
        if not names:
            continue
        positions = index.to_numpy()
        times = pd.to_datetime(out.loc[index, "event_time_local"])
        for shift in (0, 1, 3):
            when = times - pd.Timedelta(hours=shift)
            hit = (
                wide.reindex(when.to_numpy())[names].fillna(False).to_numpy(dtype=bool).any(axis=1)
            )
            any_flag[positions] |= hit
            if shift == 0:
                at_t[positions] |= hit
    out["neighbor_suspect_feature"] = any_flag
    out["neighbor_suspect_at_t"] = at_t
    return out


def _metrics_block(eval_df: pd.DataFrame, mask: pd.Series) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for split in ("train", "val", "test"):
        sub = eval_df[mask & eval_df["split"].eq(split)]
        cell: dict[str, Any] = {"n": int(len(sub))}
        if sub.empty:
            for name in MODELS:
                cell[name] = None
            cell["delta_vs_m0"] = {name: None for name in MODELS if name != "m0"}
            cell["delta_vs_m2"] = {"m5": None}
            out[split] = cell
            continue
        for name in MODELS:
            metrics = regression_metrics(sub[TARGET_COL], sub[f"y_hat_{name}"])
            metrics["mean_signed_error"] = float(sub[f"signed_{name}"].mean())
            cell[name] = metrics
        cell["delta_vs_m0"] = {
            name: _finite(cell[name]["mae"] - cell["m0"]["mae"]) for name in MODELS if name != "m0"
        }
        cell["delta_vs_m2"] = {"m5": _finite(cell["m5"]["mae"] - cell["m2"]["mae"])}
        out[split] = cell
    return out


def _error_percentiles(eval_df: pd.DataFrame, mask: pd.Series) -> list[dict[str, Any]]:
    rows = []
    for split in ("val", "test"):
        sub = eval_df[mask & eval_df["split"].eq(split)]
        row: dict[str, Any] = {"kind": "slice", "split": split, "n": int(len(sub))}
        if sub.empty:
            rows.append(row)
            continue
        for name in MODELS:
            quantiles = sub[f"abs_err_{name}"].quantile([0.5, 0.9, 0.95, 0.99])
            row[f"mae_{name}"] = float(sub[f"abs_err_{name}"].mean())
            for prob, label in ((0.5, "p50"), (0.9, "p90"), (0.95, "p95"), (0.99, "p99")):
                row[f"{label}_{name}"] = float(quantiles.loc[prob])
        row["delta_m5_m0"] = row["mae_m5"] - row["mae_m0"]
        row["delta_m5_m2"] = row["mae_m5"] - row["mae_m2"]
        row["delta_m2_m0"] = row["mae_m2"] - row["mae_m0"]
        rows.append(row)
    return rows


def _station_episodes(frame: pd.DataFrame) -> pd.DataFrame:
    """Consecutive target hours at or above 500, one station at a time. Post hoc."""
    rows = []
    episode_id = 0
    ordered = frame.sort_values(["station_name", "target_time_local"])
    for station, block in ordered.groupby("station_name", sort=False):
        times = pd.to_datetime(block["target_time_local"]).to_numpy()
        start = 0
        for index in range(len(block) + 1):
            gap = (
                index > start
                and index < len(block)
                and (times[index] - times[index - 1]) != np.timedelta64(1, "h")
            )
            if index == len(block) or gap:
                part = block.iloc[start:index]
                if len(part):
                    row = {
                        "episode": episode_id,
                        "grain": "station",
                        "station_name": station,
                        "start": str(pd.Timestamp(part["target_time_local"].min())),
                        "end": str(pd.Timestamp(part["target_time_local"].max())),
                        "n": int(len(part)),
                        "split": str(part["split"].mode().iloc[0]),
                        "diagnostic_day": bool(
                            pd.to_datetime(part["target_time_local"]).dt.date.eq(DIAGNOSTIC_DAY).any()
                        ),
                    }
                    for name in MODELS:
                        row[f"mae_{name}"] = float(part[f"abs_err_{name}"].mean())
                    row["delta_m5_m0"] = row["mae_m5"] - row["mae_m0"]
                    row["delta_m5_m2"] = row["mae_m5"] - row["mae_m2"]
                    row["delta_m2_m0"] = row["mae_m2"] - row["mae_m0"]
                    rows.append(row)
                    episode_id += 1
                start = index
    return pd.DataFrame(rows)


def _city_events(frame: pd.DataFrame) -> pd.DataFrame:
    """One event is a run of clock hours in which any station is at or above 500."""
    if frame.empty:
        return pd.DataFrame()
    times = pd.DatetimeIndex(sorted(pd.to_datetime(frame["target_time_local"]).unique()))
    cuts = np.where(np.diff(times.to_numpy()) != np.timedelta64(1, "h"))[0] + 1
    spans = np.split(times.to_numpy(), cuts)
    rows = []
    for event_id, span in enumerate(spans):
        part = frame[pd.to_datetime(frame["target_time_local"]).isin(pd.to_datetime(span))]
        row = {
            "episode": event_id,
            "grain": "city",
            "station_name": ",".join(sorted(part["station_name"].unique())),
            "start": str(pd.Timestamp(span.min())),
            "end": str(pd.Timestamp(span.max())),
            "n": int(len(part)),
            "n_stations": int(part["station_name"].nunique()),
            "split": str(part["split"].mode().iloc[0]),
            "diagnostic_day": bool(pd.Series(pd.to_datetime(span)).dt.date.eq(DIAGNOSTIC_DAY).any()),
        }
        for name in MODELS:
            row[f"mae_{name}"] = float(part[f"abs_err_{name}"].mean())
        row["delta_m5_m0"] = row["mae_m5"] - row["mae_m0"]
        row["delta_m5_m2"] = row["mae_m5"] - row["mae_m2"]
        row["delta_m2_m0"] = row["mae_m2"] - row["mae_m0"]
        rows.append(row)
    return pd.DataFrame(rows)


def _wins(frame: pd.DataFrame, column: str) -> dict[str, int]:
    if frame.empty:
        return {"better": 0, "worse": 0, "tie": 0, "n": 0}
    delta = frame[column]
    return {
        "better": int((delta < 0).sum()),
        "worse": int((delta > 0).sum()),
        "tie": int((delta == 0).sum()),
        "n": int(len(frame)),
    }


def _gate_vs_m0(metrics: dict[str, Any], n_improved: int) -> bool:
    crit = PROMOTE_CRITERIA
    needed = {
        "val": metrics["overall"]["val"]["delta_vs_m0"]["m5"],
        "test": metrics["overall"]["test"]["delta_vs_m0"]["m5"],
        "winter": metrics["winter"]["test"]["delta_vs_m0"]["m5"],
        "high_pm": metrics["high_pm"]["test"]["delta_vs_m0"]["m5"],
    }
    if any(value is None for value in needed.values()):
        return False
    return (
        needed["val"] <= crit["delta_mae_improve_threshold"]
        and needed["test"] <= crit["delta_mae_improve_threshold"]
        and needed["winter"] <= crit["no_harm_threshold"]
        and needed["high_pm"] <= crit["no_harm_threshold"]
        and n_improved >= crit["min_stations_improved_on_test"]
    )


def _decide(
    metrics: dict[str, Any],
    *,
    n_improved: int,
    reproduction_ok: bool,
    station_wins: dict[str, int],
    city_wins: dict[str, int],
) -> dict[str, Any]:
    crit = PROMOTE_CRITERIA
    suspect_val = metrics["suspect_neighbor"]["val"]["delta_vs_m2"]["m5"]
    suspect_test = metrics["suspect_neighbor"]["test"]["delta_vs_m2"]["m5"]
    suspect_test_independent = metrics["suspect_neighbor_ex_diagnostic_day"]["test"]["delta_vs_m2"]["m5"]
    normal_val = metrics["unflagged"]["val"]["delta_vs_m2"]["m5"]
    normal_test = metrics["unflagged"]["test"]["delta_vs_m2"]["m5"]
    hetero_test = metrics["large_gap_unflagged"]["test"]["delta_vs_m2"]["m5"]
    tail_m2 = metrics["ge500"]["test"]["delta_vs_m2"]["m5"]
    tail_m0 = metrics["ge500"]["test"]["delta_vs_m0"]["m5"]
    n_suspect = {
        "val": metrics["suspect_neighbor"]["val"]["n"],
        "test": metrics["suspect_neighbor"]["test"]["n"],
        "test_ex_diagnostic_day": metrics["suspect_neighbor_ex_diagnostic_day"]["test"]["n"],
    }
    suspect_benefit = (
        suspect_val is not None
        and suspect_test is not None
        and suspect_val <= crit["suspect_improve_ug"]
        and suspect_test <= crit["suspect_improve_ug"]
    )
    enough_hours = all(n_suspect[key] >= crit["min_suspect_hours"] for key in n_suspect)
    independent_benefit = (
        suspect_test_independent is not None
        and suspect_test_independent <= crit["suspect_improve_ug"]
        and n_suspect["test_ex_diagnostic_day"] >= crit["min_suspect_hours"]
    )
    normal_ok = (
        normal_val is not None
        and normal_test is not None
        and normal_val <= crit["normal_harm_ug"]
        and normal_test <= crit["normal_harm_ug"]
    )
    hetero_ok = hetero_test is not None and hetero_test <= crit["heterogeneity_harm_ug"]
    tail_ok = (
        tail_m2 is not None
        and tail_m0 is not None
        and tail_m2 <= crit["tail_vs_m2_ug"]
        and tail_m0 <= crit["tail_vs_m0_severe_ug"]
    )
    tail_research_ok = tail_m2 is not None and tail_m2 <= crit["tail_vs_m2_research_ug"]
    episode_ok = (
        station_wins["better"] >= station_wins["worse"] and city_wins["better"] >= city_wins["worse"]
    )
    overall_ok = _gate_vs_m0(metrics, n_improved)
    promote = (
        reproduction_ok
        and overall_ok
        and suspect_benefit
        and enough_hours
        and independent_benefit
        and normal_ok
        and hetero_ok
        and tail_ok
        and episode_ok
    )
    robustness_only = (
        reproduction_ok and suspect_benefit and normal_ok and tail_research_ok and not promote
    )
    if not reproduction_ok:
        decision = "KEEP_M2"
        reason = "m0_m2_reproduction_failed"
    elif promote:
        decision = "PROMOTE_CANDIDATE"
        reason = "overall_gate_and_robustness"
    elif robustness_only:
        decision = "ROBUSTNESS_ONLY"
        reason = "suspect_slice_improved_promote_gate_failed"
    elif not suspect_benefit:
        decision = "KEEP_M2"
        reason = "suspect_slice_not_stable_across_val_and_test"
    elif not normal_ok:
        decision = "KEEP_M2"
        reason = "unflagged_hours_gave_back_spatial_gain"
    else:
        decision = "KEEP_M2"
        reason = "promote_checks_incomplete"
    return {
        "decision": decision,
        "reason": reason,
        "reproduction_ok": reproduction_ok,
        "overall_gate_vs_m0": overall_ok,
        "suspect_benefit_val_and_test": suspect_benefit,
        "suspect_benefit_ex_diagnostic_day": independent_benefit,
        "enough_suspect_hours": enough_hours,
        "normal_hours_within_tolerance": normal_ok,
        "heterogeneity_within_tolerance": hetero_ok,
        "tail_within_promote_tolerance": tail_ok,
        "episode_majority_vs_m2": episode_ok,
        "stations_improved_vs_m0_test": n_improved,
        "n_suspect_hours": n_suspect,
        "station_episodes_test_ge500": station_wins,
        "city_events_test_ge500": city_wins,
    }


def _count_values(series: pd.Series) -> dict[str, int]:
    counts = series.value_counts(dropna=False).sort_index()
    return {str(int(key)): int(value) for key, value in counts.items()}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    started = _utc_now()
    frame, neighbors = _load_frame()
    print("Scoring suspect flags for post-hoc slices ...", flush=True)
    frame = _attach_suspect(frame, neighbors, _load_uci_pm25())
    null_match = {
        "t": bool(frame["neighbor_pm25_mean"].isna().equals(frame["neighbor_pm25_median"].isna())),
        "lag1": bool(
            frame["neighbor_pm25_lag1"].isna().equals(frame["neighbor_pm25_median_lag1"].isna())
        ),
        "lag3": bool(
            frame["neighbor_pm25_lag3"].isna().equals(frame["neighbor_pm25_median_lag3"].isna())
        ),
    }
    if not all(null_match.values()):
        raise RuntimeError(f"Median null pattern differs from IDW: {null_match}")

    train = frame[frame["split"] == "train"].copy()
    weights = compute_sample_weights(train["pm25_ug_m3"], train[TARGET_COL])
    feature_sets = {
        "m0": list(FEATURE_COLS_V2),
        "m2": [*FEATURE_COLS_V2, *SPATIAL_FEATURES],
        "m5": [*FEATURE_COLS_V2, *SPATIAL_MEDIAN_FEATURES],
    }
    if any("suspect" in column for column in feature_sets["m5"]):
        raise RuntimeError("Suspect flag leaked into M5 features")
    preds: dict[str, np.ndarray] = {}
    for name, columns in feature_sets.items():
        print(f"Training {name} on {len(train)} rows, {len(columns)} features ...", flush=True)
        result = run_histgb(train, frame, feature_cols=columns, sample_weight=weights)
        preds[name] = result.predictions.to_numpy()

    keep = [
        "station_key",
        "station_name",
        "event_time_local",
        "target_time_local",
        "split",
        "season",
        "pm25_ug_m3",
        TARGET_COL,
        *SPATIAL_FEATURES,
        *SPATIAL_MEDIAN_FEATURES,
        "neighbor_n_finite",
        "neighbor_n_finite_lag1",
        "neighbor_n_finite_lag3",
        "neighbor_suspect_feature",
        "neighbor_suspect_at_t",
    ]
    eval_df = frame[keep].copy()
    for name in MODELS:
        eval_df[f"y_hat_{name}"] = preds[name]
        eval_df[f"abs_err_{name}"] = (eval_df[TARGET_COL] - eval_df[f"y_hat_{name}"]).abs()
        eval_df[f"signed_{name}"] = eval_df[f"y_hat_{name}"] - eval_df[TARGET_COL]

    eval_df["winter"] = eval_df["season"].astype(str).str.lower().eq("winter")
    eval_df["heating"] = statutory_heating_mask(eval_df["event_time_local"])
    change = eval_df[TARGET_COL] - eval_df["pm25_ug_m3"]
    eval_df["rapid_rise"] = change >= PROMOTE_CRITERIA["rapid_change_ug_m3"]
    eval_df["rapid_drop"] = change <= -PROMOTE_CRITERIA["rapid_change_ug_m3"]
    eval_df["large_gap"] = eval_df["spatial_gradient_median"].abs() >= LARGE_GAP_UG
    on_diagnostic_day = eval_df["event_time_local"].dt.date.eq(DIAGNOSTIC_DAY) | eval_df[
        "target_time_local"
    ].dt.date.eq(DIAGNOSTIC_DAY)
    masks = {
        "overall": pd.Series(True, index=eval_df.index),
        "winter": eval_df["winter"],
        "heating": eval_df["heating"],
        "high_pm": eval_df[TARGET_COL] >= PROMOTE_CRITERIA["high_pm_threshold"],
        "ge500": eval_df[TARGET_COL] >= EXTREME_UG,
        "rapid_rise": eval_df["rapid_rise"],
        "rapid_drop": eval_df["rapid_drop"],
        "suspect_neighbor": eval_df["neighbor_suspect_feature"],
        "suspect_neighbor_at_t": eval_df["neighbor_suspect_at_t"],
        "suspect_neighbor_ex_diagnostic_day": eval_df["neighbor_suspect_feature"] & ~on_diagnostic_day,
        "unflagged": ~eval_df["neighbor_suspect_feature"],
        "large_gap_unflagged": eval_df["large_gap"] & ~eval_df["neighbor_suspect_feature"],
        "ordinary_unflagged": ~eval_df["large_gap"] & ~eval_df["neighbor_suspect_feature"],
    }
    metrics = {name: _metrics_block(eval_df, mask) for name, mask in masks.items()}

    test = eval_df[eval_df["split"].eq("test")]
    station_rows = []
    for station, sub in test.groupby("station_name", sort=True):
        row: dict[str, Any] = {"station_name": station, "n": int(len(sub))}
        for name in MODELS:
            row[f"mae_{name}"] = float(sub[f"abs_err_{name}"].mean())
        row["delta_m5_m0"] = row["mae_m5"] - row["mae_m0"]
        row["delta_m5_m2"] = row["mae_m5"] - row["mae_m2"]
        row["delta_m2_m0"] = row["mae_m2"] - row["mae_m0"]
        winter = sub[sub["winter"]]
        row["n_winter"] = int(len(winter))
        if len(winter):
            for name in MODELS:
                row[f"mae_{name}_winter"] = float(winter[f"abs_err_{name}"].mean())
            row["delta_m5_m2_winter"] = row["mae_m5_winter"] - row["mae_m2_winter"]
        station_rows.append(row)
    stations_df = pd.DataFrame(station_rows)
    n_improved = int((stations_df["delta_m5_m0"] < 0).sum())

    m0_gap = abs(metrics["overall"]["test"]["m0"]["mae"] - REF_M0_TEST_MAE)
    m2_gap = abs(metrics["overall"]["test"]["m2"]["mae"] - REF_M2_TEST_MAE)
    m0_winter_gap = abs(metrics["winter"]["test"]["m0"]["mae"] - REF_M0_WINTER_TEST_MAE)
    m2_winter_gap = abs(metrics["winter"]["test"]["m2"]["mae"] - REF_M2_WINTER_TEST_MAE)
    reproduction_ok = max(m0_gap, m2_gap, m0_winter_gap, m2_winter_gap) <= REPRO_TOLERANCE

    ge500 = eval_df[eval_df[TARGET_COL] >= EXTREME_UG]
    episodes = _station_episodes(ge500)
    events = _city_events(ge500)
    test_episodes = episodes[episodes["split"].eq("test")] if len(episodes) else episodes
    test_events = events[events["split"].eq("test")] if len(events) else events
    decision = _decide(
        metrics,
        n_improved=n_improved,
        reproduction_ok=reproduction_ok,
        station_wins=_wins(test_episodes, "delta_m5_m2"),
        city_wins=_wins(test_events, "delta_m5_m2"),
    )

    robustness_rows: list[dict[str, Any]] = []
    for slice_name in (
        "suspect_neighbor",
        "suspect_neighbor_at_t",
        "suspect_neighbor_ex_diagnostic_day",
        "unflagged",
        "ordinary_unflagged",
        "large_gap_unflagged",
        "ge500",
        "overall",
    ):
        for row in _error_percentiles(eval_df, masks[slice_name]):
            row["slice"] = slice_name
            robustness_rows.append(row)
    test_gap = eval_df["abs_err_m5"] - eval_df["abs_err_m2"]
    ranked = eval_df[eval_df["split"].eq("test")].assign(delta_m5_m2=test_gap)
    for label, part in (
        ("largest_improvement", ranked.nsmallest(10, "delta_m5_m2")),
        ("largest_degradation", ranked.nlargest(10, "delta_m5_m2")),
    ):
        for record in part.itertuples(index=False):
            robustness_rows.append(
                {
                    "kind": label,
                    "slice": label,
                    "split": "test",
                    "station_name": record.station_name,
                    "event_time_local": str(record.event_time_local),
                    "target_time_local": str(record.target_time_local),
                    "pm25_ug_m3": float(record.pm25_ug_m3),
                    "y_pm25_tplus1": float(getattr(record, TARGET_COL)),
                    "neighbor_suspect_feature": bool(record.neighbor_suspect_feature),
                    "large_gap": bool(record.large_gap),
                    "mae_m0": float(record.abs_err_m0),
                    "mae_m2": float(record.abs_err_m2),
                    "mae_m5": float(record.abs_err_m5),
                    "delta_m5_m2": float(record.delta_m5_m2),
                    "n": 1,
                }
            )

    gucheng = eval_df[
        eval_df["station_name"].eq("Gucheng")
        & (
            eval_df["event_time_local"].dt.date.eq(DIAGNOSTIC_DAY)
            | eval_df["target_time_local"].dt.date.eq(DIAGNOSTIC_DAY)
        )
    ].sort_values("target_time_local")
    gucheng_neighbors = neighbors[neighbors["station_name"].eq("Gucheng")].sort_values("neighbor_rank")
    wide = frame.pivot_table(
        index="event_time_local", columns="station_name", values="pm25_ug_m3", aggfunc="last"
    )
    case_rows = []
    for record in gucheng.itertuples(index=False):
        case = {
            "role": "diagnostic_only",
            "event_time_local": str(record.event_time_local),
            "target_time_local": str(record.target_time_local),
            "pm25_ug_m3": float(record.pm25_ug_m3),
            "y_pm25_tplus1": float(getattr(record, TARGET_COL)),
            "neighbor_idw_mean": _finite(record.neighbor_pm25_mean),
            "neighbor_median": _finite(record.neighbor_pm25_median),
            "neighbor_suspect_feature": bool(record.neighbor_suspect_feature),
            "neighbor_suspect_at_t": bool(record.neighbor_suspect_at_t),
        }
        moment = pd.Timestamp(record.event_time_local)
        for rank, neighbor in enumerate(gucheng_neighbors.itertuples(index=False), start=1):
            value = wide[neighbor.neighbor_name].get(moment, np.nan) if neighbor.neighbor_name in wide else np.nan
            case[f"neighbor_{rank}_name"] = neighbor.neighbor_name
            case[f"neighbor_{rank}_pm25"] = _finite(value)
        for name in MODELS:
            case[f"y_hat_{name}"] = float(getattr(record, f"y_hat_{name}"))
            case[f"abs_err_{name}"] = float(getattr(record, f"abs_err_{name}"))
            case[f"signed_{name}"] = float(getattr(record, f"signed_{name}"))
        case_rows.append(case)

    worst_station = None
    if len(test_episodes):
        worst = test_episodes.sort_values("delta_m5_m0", ascending=False).iloc[0]
        worst_vs_m2 = test_episodes.sort_values("delta_m5_m2", ascending=False).iloc[0]
        worst_station = {
            "largest_degradation_vs_m0": worst.to_dict(),
            "largest_degradation_vs_m2": worst_vs_m2.to_dict(),
        }

    report = {
        "ok": True,
        "phase": "robust_spatial_m5_poc",
        "started_at": started,
        "finished_at": _utc_now(),
        "decision": decision,
        "locked_reference": {
            "algorithm": "hist_gradient_boosting",
            "random_state": RANDOM_STATE,
            "model_lock_untouched": True,
            "feature_sets": feature_sets,
            "idw_features_replaced": list(SPATIAL_FEATURES),
            "median_features": list(SPATIAL_MEDIAN_FEATURES),
            "sample_weight": {
                "threshold": SAMPLE_WEIGHT_THRESHOLD,
                "high_weight": SAMPLE_WEIGHT_HIGH,
            },
            "split": {
                "train_end": TRAIN_END,
                "val": [VAL_START, VAL_END],
                "test": [TEST_START, TEST_END],
            },
        },
        "reproduction": {
            "ok": reproduction_ok,
            "tolerance": REPRO_TOLERANCE,
            "m0_test_mae": metrics["overall"]["test"]["m0"]["mae"],
            "m2_test_mae": metrics["overall"]["test"]["m2"]["mae"],
            "m0_winter_test_mae": metrics["winter"]["test"]["m0"]["mae"],
            "m2_winter_test_mae": metrics["winter"]["test"]["m2"]["mae"],
            "abs_gap": {
                "m0_test": m0_gap,
                "m2_test": m2_gap,
                "m0_winter_test": m0_winter_gap,
                "m2_winter_test": m2_winter_gap,
            },
            "reference": {
                "m0_test": REF_M0_TEST_MAE,
                "m2_test": REF_M2_TEST_MAE,
                "m0_winter_test": REF_M0_WINTER_TEST_MAE,
                "m2_winter_test": REF_M2_WINTER_TEST_MAE,
            },
        },
        "leakage": {
            "spatial": (
                "M2 reads the inverse-distance mean of the three nearest stations "
                "at t, t-1h and t-3h, and own PM2.5(t) minus the mean at t. "
                "M5 reads the median of that same block at those same clocks, "
                "and own PM2.5(t) minus the median at t. "
                "Neighbor PM2.5 at t+1 is not read. The suspect flag is not a feature."
            ),
            "same_row_set": True,
            "rows": int(len(frame)),
            "median_null_matches_idw": null_match,
            "neighbor_n_finite_t": _count_values(frame["neighbor_n_finite"]),
            "neighbor_n_finite_lag1": _count_values(frame["neighbor_n_finite_lag1"]),
            "neighbor_n_finite_lag3": _count_values(frame["neighbor_n_finite_lag3"]),
            "high_pm_extremes_and_flags_are_post_hoc": True,
            "diagnostic_day_not_a_fitting_target": str(DIAGNOSTIC_DAY),
        },
        "promote_criteria_preregistered": PROMOTE_CRITERIA,
        "data": {
            "matrix": "artifacts/forecasting/feature_matrix_v2.parquet",
            "n_rows": int(len(frame)),
            "n_train": int(len(train)),
            "n_val": int(frame["split"].eq("val").sum()),
            "n_test": int(frame["split"].eq("test").sum()),
        },
        "metrics": metrics,
        "stations_test": station_rows,
        "episode_summary_test_ge500": {
            "station": _wins(test_episodes, "delta_m5_m2"),
            "station_vs_m0": _wins(test_episodes, "delta_m5_m0"),
            "city": _wins(test_events, "delta_m5_m2"),
            "city_vs_m0": _wins(test_events, "delta_m5_m0"),
            "worst": worst_station,
        },
    }
    pred_cols = [
        "station_name",
        "event_time_local",
        "target_time_local",
        "split",
        "pm25_ug_m3",
        TARGET_COL,
        "neighbor_pm25_mean",
        "neighbor_pm25_median",
        "neighbor_suspect_feature",
        "y_hat_m0",
        "y_hat_m2",
        "y_hat_m5",
        "abs_err_m0",
        "abs_err_m2",
        "abs_err_m5",
        "signed_m0",
        "signed_m2",
        "signed_m5",
    ]
    eval_df.loc[:, pred_cols].to_csv(OUT / "predictions_comparison.csv", index=False)
    pd.DataFrame(robustness_rows).to_csv(OUT / "robustness_analysis.csv", index=False)
    episode_out = pd.concat([episodes, events], ignore_index=True) if len(episodes) or len(events) else pd.DataFrame()
    episode_out.to_csv(OUT / "episode_comparison.csv", index=False)
    pd.DataFrame(case_rows).to_csv(OUT / "gucheng_case_study.csv", index=False)
    stations_df.to_csv(OUT / "delta_mae_by_station_test.csv", index=False)
    report_path = OUT / "ablation_report.json"
    report_path.write_text(json.dumps(report, indent=2, allow_nan=True, default=str) + "\n", encoding="utf-8")
    summary = {
        "decision": decision["decision"],
        "reason": decision["reason"],
        "reproduction_ok": reproduction_ok,
        "delta_m5_m0_test": metrics["overall"]["test"]["delta_vs_m0"]["m5"],
        "delta_m5_m2_test": metrics["overall"]["test"]["delta_vs_m2"]["m5"],
        "delta_m5_m2_suspect_test": metrics["suspect_neighbor"]["test"]["delta_vs_m2"]["m5"],
        "delta_m5_m2_suspect_val": metrics["suspect_neighbor"]["val"]["delta_vs_m2"]["m5"],
        "delta_m5_m2_unflagged_test": metrics["unflagged"]["test"]["delta_vs_m2"]["m5"],
        "delta_m5_m2_ge500_test": metrics["ge500"]["test"]["delta_vs_m2"]["m5"],
        "report": str(report_path.relative_to(ROOT)).replace("\\", "/"),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
