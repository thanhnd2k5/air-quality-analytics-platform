#!/usr/bin/env python3
"""Six-hour episode-onset comparison.

The label, the false-alarm budgets, and the recall margin live in
src/classification/onset.py. They were fixed before this run. The script
does not write the alert lock, the regression lock, or the cluster lock.
2016 H2 is scored with thresholds chosen on 2016 H1 and is not a fresh holdout.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.diagnose_evaluation_hygiene import (  # noqa: E402
    MATRIX,
    NO_CLUSTER_COLS,
    STATIONS,
    load_uci_hourly,
)
from src.classification.constants import FEATURE_COLS, RANDOM_STATE  # noqa: E402
from src.classification.label_window import (  # noqa: E402
    DEVELOPMENT_FOLDS,
    PUBLISHED_SPLIT_ENDS,
    assign_time_fold,
    rows_inside_split,
    split_ends_for_fold,
)
from src.classification.models import HISTGB_CAT_COLS, feature_frame  # noqa: E402
from src.classification.onset import (  # noqa: E402
    LEVEL_GRID,
    ONSET_CONFIRM_HOURS,
    PRIMARY_FA_PER_STATION_DAY,
    PROBABILITY_GRID,
    RECALL_MARGIN,
    SENSITIVITY_FA_PER_STATION_DAY,
    TREND_GRID,
    choose_operating_point,
    clears_recall_margin,
    episode_metrics,
    fold_support,
    mark_onset_origins,
    trend_score,
)
from src.clustering.window_profiles import meteorological_season  # noqa: E402
from src.forecasting.constants import TEST_END, TEST_START  # noqa: E402
from src.forecasting.spatial_calendar import SPATIAL_FEATURES, add_spatial_features  # noqa: E402

OUT = ROOT / "artifacts" / "classification" / "onset_6h"
SPATIAL_COLS = NO_CLUSTER_COLS + list(SPATIAL_FEATURES)
LEARNED = ("histgb_cluster", "histgb_local", "histgb_spatial")
BUDGETS = (
    ("primary", PRIMARY_FA_PER_STATION_DAY),
    ("sensitivity", SENSITIVITY_FA_PER_STATION_DAY),
)


def _jsonable(value):
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if np.isfinite(number) else None
    return value


def _fit_proba(frame: pd.DataFrame, feature_cols: list[str]) -> np.ndarray:
    train = (frame["split"] == "train").to_numpy()
    y = frame["y_onset"].to_numpy(dtype=int)
    if len(np.unique(y[train])) < 2:
        raise ValueError("train onset labels have a single class")
    features = feature_frame(frame, feature_cols)
    model = HistGradientBoostingClassifier(
        max_depth=8,
        max_iter=200,
        learning_rate=0.08,
        min_samples_leaf=40,
        l2_regularization=0.1,
        random_state=RANDOM_STATE,
        categorical_features=[
            list(feature_cols).index(column)
            for column in HISTGB_CAT_COLS
            if column in feature_cols
        ],
    ).fit(features.iloc[np.flatnonzero(train)], y[train])
    return model.predict_proba(features)[:, 1]


def _fold_frame(marked: pd.DataFrame, fold, *, include_test: bool) -> pd.DataFrame:
    split = assign_time_fold(marked["event_time_local"], fold)
    if include_test:
        times = pd.to_datetime(marked["event_time_local"])
        split.loc[(times >= pd.Timestamp(TEST_START)) & (times <= pd.Timestamp(TEST_END))] = "test"
    ends = split_ends_for_fold(fold)
    if include_test:
        ends = {**ends, "test": TEST_END}
    inside = rows_inside_split(
        marked["event_time_local"],
        split,
        ends,
        label_hours=ONSET_CONFIRM_HOURS,
    )
    keep = inside.to_numpy() & marked["y_onset"].notna().to_numpy()
    out = marked.loc[keep].copy()
    out["split"] = split.loc[keep].astype(str).to_numpy()
    return out.reset_index(drop=True)


def _rows_for_threshold(fold: str, variant: str, budget: str, threshold, budget_met: bool, frame, pred) -> list[dict]:
    rows = []
    for split in ("train", "val", "test"):
        mask = (frame["split"] == split).to_numpy()
        if not mask.any():
            continue
        metrics = episode_metrics(frame.loc[mask], np.asarray(pred)[mask])
        rows.append(
            {
                "fold": fold,
                "variant": variant,
                "budget": budget,
                "split": split,
                "threshold": threshold,
                "budget_met": budget_met,
                **metrics,
            }
        )
    return rows


def _apply_budget(fold: str, variant: str, score, grid, frame) -> tuple[list[dict], np.ndarray]:
    val = frame["split"] == "val"
    val_score = np.asarray(score, dtype=float)[val.to_numpy()]
    val_frame = frame.loc[val].reset_index(drop=True)
    primary_pred = None
    rows: list[dict] = []
    for budget_name, fa_budget in BUDGETS:
        chosen = choose_operating_point(val_score, val_frame, grid, fa_budget)
        pred = (np.asarray(score, dtype=float) >= chosen["threshold"]).astype(int)
        if budget_name == "primary":
            primary_pred = pred
        rows.extend(
            _rows_for_threshold(
                fold,
                variant,
                budget_name,
                chosen["threshold"],
                chosen["budget_met"],
                frame,
                pred,
            )
        )
        print(
            f"  {variant} {budget_name} cut={chosen['threshold']} "
            f"val_recall={chosen['metrics']['episode_recall']:.3f} "
            f"fa/day={chosen['metrics']['fa_per_station_day']:.3f} "
            f"met={chosen['budget_met']}",
            flush=True,
        )
    return rows, primary_pred


def _episode_table(frame: pd.DataFrame, pred: np.ndarray, variant: str, split: str) -> pd.DataFrame:
    mask = ((frame["split"] == split) & (frame["y_onset"] == 1)).to_numpy()
    part = frame.loc[mask].copy()
    if part.empty:
        return pd.DataFrame()
    part["detected"] = np.asarray(pred)[mask]
    grouped = part.groupby(["station_key", "episode_start"], as_index=False).agg(
        detected=("detected", "max"),
        station_name=("station_name", "first"),
        episode_duration_h=("episode_duration_h", "first"),
        episode_peak=("episode_peak", "first"),
        episode_season=("episode_season", "first"),
        max_lead_h=("lead_hours", "max"),
        n_alerts=("detected", "sum"),
    )
    grouped.insert(0, "split", split)
    grouped.insert(0, "variant", variant)
    grouped["duration_bin"] = pd.cut(
        grouped["episode_duration_h"],
        bins=[2, 5, 11, np.inf],
        labels=["3-5", "6-11", "12+"],
    ).astype(str)
    return grouped


def _group_summary(episodes: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for column in ("station_name", "episode_season", "duration_bin"):
        for keys, group in episodes.groupby(["variant", "split", column], sort=False):
            variant, split, name = keys
            detected = int(group["detected"].sum())
            n = int(len(group))
            rows.append(
                {
                    "variant": variant,
                    "split": split,
                    "group_type": column,
                    "group": name,
                    "n_episodes": n,
                    "n_detected": detected,
                    "episode_recall": float(detected / n) if n else None,
                }
            )
    return pd.DataFrame(rows)


def _lookup(metrics: pd.DataFrame, fold: str, variant: str, split: str, budget: str) -> pd.Series:
    match = metrics[
        (metrics["fold"] == fold)
        & (metrics["variant"] == variant)
        & (metrics["split"] == split)
        & (metrics["budget"] == budget)
    ]
    if match.empty:
        raise KeyError(f"missing metrics {fold} {variant} {split} {budget}")
    return match.iloc[0]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print("load hourly and matrix", flush=True)
    hourly = load_uci_hourly()
    stations = pd.read_csv(STATIONS)
    matrix = pd.read_parquet(MATRIX)
    if "station_name" not in matrix.columns:
        names = stations.rename(columns={"station_id": "station_key"})[
            ["station_key", "station_name"]
        ]
        matrix = matrix.merge(names, on="station_key", how="left")
    print("spatial features", flush=True)
    with_spatial, _neighbors = add_spatial_features(matrix, stations)
    print("onset labels", flush=True)
    marked = mark_onset_origins(with_spatial, hourly[["station_key", "event_time_local", "pm25_ug_m3"]])
    season = pd.Series(pd.NA, index=marked.index, dtype="string")
    has_episode = marked["episode_start"].notna()
    season.loc[has_episode] = meteorological_season(
        marked.loc[has_episode, "episode_start"].dt.month
    ).to_numpy()
    marked["episode_season"] = season
    marked["trend_score"] = trend_score(marked["pm25_ug_m3"], marked["pm25_delta_1"])

    published_inside = rows_inside_split(
        marked["event_time_local"],
        marked["split"],
        PUBLISHED_SPLIT_ENDS,
        label_hours=ONSET_CONFIRM_HOURS,
    )
    census = []
    for split_name in ("train", "val", "test"):
        in_split = (marked["split"] == split_name).to_numpy()
        eligible = in_split & published_inside.to_numpy() & marked["y_onset"].notna().to_numpy()
        census.append(
            {
                "split": split_name,
                "n_rows": int(in_split.sum()),
                "n_eligible": int(eligible.sum()),
                "n_positive": int(marked.loc[eligible, "y_onset"].sum()),
            }
        )
        print(census[-1], flush=True)

    metric_rows: list[dict] = []
    episode_frames: list[pd.DataFrame] = []
    baselines: dict[str, str] = {}
    for fold in DEVELOPMENT_FOLDS:
        include_test = fold.name == "2016h1"
        frame = _fold_frame(marked, fold, include_test=include_test)
        print(
            f"fold {fold.name} rows={len(frame):,} "
            f"positives={int(frame['y_onset'].sum()):,}",
            flush=True,
        )
        zero = np.zeros(len(frame), dtype=int)
        metric_rows.extend(
            _rows_for_threshold(fold.name, "persistence", "primary", None, True, frame, zero)
        )
        level_rows, level_pred = _apply_budget(
            fold.name, "level", frame["pm25_ug_m3"], LEVEL_GRID, frame
        )
        trend_rows, trend_pred = _apply_budget(
            fold.name, "trend", frame["trend_score"], TREND_GRID, frame
        )
        metric_rows.extend(level_rows)
        metric_rows.extend(trend_rows)
        running = pd.DataFrame(metric_rows)
        level_recall = float(
            _lookup(running, fold.name, "level", "val", "primary")["episode_recall"]
        )
        trend_recall = float(
            _lookup(running, fold.name, "trend", "val", "primary")["episode_recall"]
        )
        baselines[fold.name] = "trend" if trend_recall > level_recall else "level"
        print(f"  baseline {baselines[fold.name]}", flush=True)

        learned_pred = {}
        for variant, columns in (
            ("histgb_cluster", list(FEATURE_COLS)),
            ("histgb_local", list(NO_CLUSTER_COLS)),
            ("histgb_spatial", list(SPATIAL_COLS)),
        ):
            print(f"fit {fold.name} / {variant}", flush=True)
            proba = _fit_proba(frame, columns)
            rows, pred = _apply_budget(fold.name, variant, proba, PROBABILITY_GRID, frame)
            metric_rows.extend(rows)
            learned_pred[variant] = pred
        if include_test:
            for variant, pred in learned_pred.items():
                for split_name in ("val", "test"):
                    episode_frames.append(_episode_table(frame, pred, variant, split_name))
            base_name = baselines[fold.name]
            base_pred = trend_pred if base_name == "trend" else level_pred
            for split_name in ("val", "test"):
                episode_frames.append(_episode_table(frame, base_pred, base_name, split_name))

    metrics = pd.DataFrame(metric_rows)
    metrics.to_csv(OUT / "onset_metrics.csv", index=False)
    decisions = []
    for variant in LEARNED:
        clears = []
        for fold in DEVELOPMENT_FOLDS:
            model_recall = float(
                _lookup(metrics, fold.name, variant, "val", "primary")["episode_recall"]
            )
            base_recall = float(
                _lookup(metrics, fold.name, baselines[fold.name], "val", "primary")["episode_recall"]
            )
            clears.append(clears_recall_margin(model_recall, base_recall, RECALL_MARGIN))
        test_clear = None
        if "2016h1" in baselines:
            test_model = _lookup(metrics, "2016h1", variant, "test", "primary")
            test_base = _lookup(metrics, "2016h1", baselines["2016h1"], "test", "primary")
            test_clear = clears_recall_margin(
                float(test_model["episode_recall"]),
                float(test_base["episode_recall"]),
                RECALL_MARGIN,
            )
        local_clears = []
        for fold in DEVELOPMENT_FOLDS:
            spatial_recall = float(
                _lookup(metrics, fold.name, "histgb_spatial", "val", "primary")["episode_recall"]
            )
            local_recall = float(
                _lookup(metrics, fold.name, "histgb_local", "val", "primary")["episode_recall"]
            )
            local_clears.append(clears_recall_margin(spatial_recall, local_recall, RECALL_MARGIN))
        decisions.append(
            {
                "variant": variant,
                "baseline_by_fold": baselines,
                "val_clears_baseline": clears,
                "val_supported": fold_support(clears),
                "test_clears_baseline": test_clear,
                "spatial_clears_local_on_val": local_clears if variant == "histgb_spatial" else None,
                "spatial_supported_over_local": fold_support(local_clears) if variant == "histgb_spatial" else None,
            }
        )

    episodes = pd.concat(episode_frames, ignore_index=True) if episode_frames else pd.DataFrame()
    if not episodes.empty:
        episodes.to_csv(OUT / "confirmation_episodes.csv", index=False)
        _group_summary(episodes).to_csv(OUT / "confirmation_groups.csv", index=False)
    report = {
        "question": "PM2.5(t) < 115 and an episode of at least 3 hours starts in t+1..t+6",
        "confirm_hours": ONSET_CONFIRM_HOURS,
        "primary_fa_per_station_day": PRIMARY_FA_PER_STATION_DAY,
        "sensitivity_fa_per_station_day": SENSITIVITY_FA_PER_STATION_DAY,
        "recall_margin": RECALL_MARGIN,
        "published_split_census": census,
        "baselines": baselines,
        "decisions": decisions,
        "unchanged": [
            "artifacts/classification/model_lock.json",
            "artifacts/clustering/cluster_lock.json",
            "artifacts/forecasting/model_lock.json",
        ],
    }
    (OUT / "onset_report.json").write_text(json.dumps(_jsonable(report), indent=2), encoding="utf-8")
    print(f"wrote {OUT}", flush=True)


if __name__ == "__main__":
    main()
