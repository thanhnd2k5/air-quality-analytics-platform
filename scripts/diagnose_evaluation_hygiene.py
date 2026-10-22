#!/usr/bin/env python3
"""Before/after check for cluster leakage and labels that cross a split.

Fits station clusters on each development fold's train window and refits the
alert classifier on rows whose label stays inside that split. Does not write
the classification lock, the regression lock, or the published cluster lock.

The fold calendar and the eight-hour onset cutoff live in
src/classification/label_window.py. They were fixed before this run.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.classification.constants import (  # noqa: E402
    ALERT_TARGET_COL,
    ALERT_THRESHOLD,
    FEATURE_COLS,
)
from src.classification.label_window import (  # noqa: E402
    DEVELOPMENT_FOLDS,
    LABEL_CENSUS_HOURS,
    ONSET_CONFIRM_HOURS,
    POINT_LABEL_HOURS,
    PUBLISHED_SPLIT_ENDS,
    assign_time_fold,
    rows_inside_split,
    split_ends_for_fold,
)
from src.classification.metrics import onset_recall  # noqa: E402
from src.classification.models import run_histgb  # noqa: E402
from src.classification.target import add_alert_target  # noqa: E402
from src.clustering.profiles import CLUSTER_FEATURE_COLS  # noqa: E402
from src.clustering.window_profiles import (  # noqa: E402
    assignment_agreement,
    fit_window_clusters,
    station_profiles,
)
from src.forecasting.constants import (  # noqa: E402
    ML_END,
    ML_START,
    TEST_END,
    TEST_START,
)

OUT = ROOT / "artifacts" / "classification" / "evaluation_hygiene"
UCI_DIR = ROOT / "data" / "raw" / "uci"
STATIONS = ROOT / "data" / "raw" / "reference" / "stations.csv"
LOCKED_ASSIGNMENT = ROOT / "data" / "clustering" / "station_cluster_assignment.csv"
LOCKED_PROFILES = ROOT / "artifacts" / "clustering" / "station_profiles.csv"
MATRIX = ROOT / "artifacts" / "forecasting" / "feature_matrix_v2.parquet"
PUBLISHED_METRICS = ROOT / "artifacts" / "classification" / "metrics.csv"
PROFILE_WINDOW = {"window_start": ML_START, "window_end": ML_END}
NO_CLUSTER_COLS = [column for column in FEATURE_COLS if column != "cluster_id"]


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
    if isinstance(value, pd.DataFrame):
        return _jsonable(value.to_dict(orient="records"))
    return value


def load_uci_hourly() -> pd.DataFrame:
    stations = pd.read_csv(STATIONS)
    stations = stations.rename(columns={"station_id": "station_key"})
    frames: list[pd.DataFrame] = []
    for path in sorted(UCI_DIR.glob("PRSA_Data_*.csv")):
        raw = pd.read_csv(path, na_values=["NA"])
        raw["event_time_local"] = pd.to_datetime(dict(year=raw.year, month=raw.month, day=raw.day, hour=raw.hour))
        frames.append(
            raw.rename(
                columns={
                    "PM2.5": "pm25_ug_m3",
                    "PM10": "pm10_ug_m3",
                    "SO2": "so2_ug_m3",
                    "NO2": "no2_ug_m3",
                    "CO": "co_ug_m3",
                    "O3": "o3_ug_m3",
                    "station": "station_name",
                }
            )
        )
    hourly = pd.concat(frames, ignore_index=True)
    hourly = hourly.merge(
        stations[["station_key", "station_name", "district"]],
        on="station_name",
        how="left",
        validate="many_to_one",
    )
    if hourly["station_key"].isna().any():
        missing = sorted(hourly.loc[hourly["station_key"].isna(), "station_name"].unique())
        raise ValueError(f"UCI station names missing from the reference list: {missing}")
    return hourly


def profile_deltas(built: pd.DataFrame, reference: pd.DataFrame) -> dict[str, float]:
    merged = built.merge(reference, on="station_key", suffixes=("_built", "_ref"))
    deltas = {}
    for column in CLUSTER_FEATURE_COLS:
        deltas[column] = float((merged[f"{column}_built"] - merged[f"{column}_ref"]).abs().max())
    return deltas


def leakage_census(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    stored = rows_inside_split(
        frame["event_time_local"],
        frame["split"],
        PUBLISHED_SPLIT_ENDS,
        label_hours=POINT_LABEL_HOURS,
        deadline=frame["target_time_local"],
    )
    for split, end in PUBLISHED_SPLIT_ENDS.items():
        mask = frame["split"] == split
        rows.append(
            {
                "rule": "stored_target_time",
                "label_hours": POINT_LABEL_HOURS,
                "split": split,
                "split_end": end,
                "n_rows": int(mask.sum()),
                "n_outside": int((mask & ~stored).sum()),
                "n_inside": int((mask & stored).sum()),
            }
        )
    for hours in LABEL_CENSUS_HOURS:
        inside = rows_inside_split(
            frame["event_time_local"],
            frame["split"],
            PUBLISHED_SPLIT_ENDS,
            label_hours=hours,
        )
        for split, end in PUBLISHED_SPLIT_ENDS.items():
            mask = frame["split"] == split
            rows.append(
                {
                    "rule": "origin_plus_hours",
                    "label_hours": hours,
                    "split": split,
                    "split_end": end,
                    "n_rows": int(mask.sum()),
                    "n_outside": int((mask & ~inside).sum()),
                    "n_inside": int((mask & inside).sum()),
                }
            )
    return pd.DataFrame(rows)


def apply_cluster(frame: pd.DataFrame, assignment: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    mapping = assignment.set_index("station_key")["cluster_id"]
    out["cluster_id"] = out["station_key"].map(mapping)
    if out["cluster_id"].isna().any():
        missing = sorted(out.loc[out["cluster_id"].isna(), "station_key"].unique().tolist())
        raise ValueError(f"stations missing a cluster: {missing}")
    out["cluster_id"] = out["cluster_id"].astype(int)
    return out


def score_frame(name: str, fold: str, frame: pd.DataFrame, feature_cols: list[str]) -> list[dict]:
    print(f"fit {fold} / {name}  rows={len(frame):,}", flush=True)
    result = run_histgb(frame, feature_cols=feature_cols)
    rows = []
    for split, metrics in result.metrics.items():
        mask = (frame["split"] == split).to_numpy()
        onset = onset_recall(
            frame.loc[mask, "pm25_ug_m3"],
            frame.loc[mask, ALERT_TARGET_COL],
            result.pred[mask],
            ALERT_THRESHOLD,
        )
        rows.append(
            {
                "fold": fold,
                "variant": name,
                "split": split,
                "n": metrics["n"],
                "threshold": result.threshold,
                "f1": metrics["f1"],
                "precision": metrics["precision"],
                "recall": metrics["recall"],
                "onsets": onset["onsets"],
                "onset_detected": onset["detected"],
                "onset_recall": onset["recall"],
            }
        )
    return rows


def purged_fold_frame(labeled: pd.DataFrame, fold, *, include_test: bool) -> pd.DataFrame:
    split = assign_time_fold(labeled["event_time_local"], fold)
    if include_test:
        times = pd.to_datetime(labeled["event_time_local"])
        split.loc[(times >= pd.Timestamp(TEST_START)) & (times <= pd.Timestamp(TEST_END))] = "test"
    ends = split_ends_for_fold(fold)
    if include_test:
        ends = {**ends, "test": TEST_END}
    keep = rows_inside_split(
        labeled["event_time_local"],
        split,
        ends,
        label_hours=POINT_LABEL_HOURS,
        deadline=labeled["target_time_local"],
    )
    out = labeled.loc[keep].copy()
    out["split"] = split.loc[keep].to_numpy()
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    hourly = load_uci_hourly()
    reference = pd.read_csv(LOCKED_PROFILES)
    locked = pd.read_csv(LOCKED_ASSIGNMENT)
    full_continued = station_profiles(hourly, episode_mode="start_in_window", **PROFILE_WINDOW)
    full_inside = station_profiles(hourly, episode_mode="inside", **PROFILE_WINDOW)
    continued_fit = fit_window_clusters(full_continued)
    inside_fit = fit_window_clusters(full_inside)
    cluster_report = {
        "profile_delta_max_abs": {
            "start_in_window": profile_deltas(full_continued, reference),
            "inside": profile_deltas(full_inside, reference),
        },
        "full_window_start_in_window_vs_lock": assignment_agreement(
            continued_fit["assignment"], locked
        ),
        "full_window_inside_vs_lock": assignment_agreement(inside_fit["assignment"], locked),
        "full_window_k_by_silhouette": {
            "start_in_window": continued_fit["k_by_silhouette"],
            "inside": inside_fit["k_by_silhouette"],
        },
        "folds": [],
    }
    fold_assignments = {}
    for fold in DEVELOPMENT_FOLDS:
        profiles = station_profiles(
            hourly,
            window_start=ML_START,
            window_end=fold.train_end,
            episode_mode="inside",
        )
        fitted = fit_window_clusters(profiles)
        agreement = assignment_agreement(fitted["assignment"], locked)
        fold_assignments[fold.name] = fitted["assignment"]
        cluster_report["folds"].append(
            {
                "fold": fold.name,
                "train_end": fold.train_end,
                "k_by_silhouette": fitted["k_by_silhouette"],
                "vs_lock": agreement,
            }
        )
        print(
            f"cluster {fold.name}: agreement={agreement['pairwise_agreement']:.3f} "
            f"moved={agreement['moved_stations']}",
            flush=True,
        )

    matrix = pd.read_parquet(MATRIX)
    labeled = add_alert_target(matrix, horizon=POINT_LABEL_HOURS)
    labeled["target_time_local"] = pd.to_datetime(labeled["target_time_local"])
    labeled["event_time_local"] = pd.to_datetime(labeled["event_time_local"])
    same_clock = labeled["target_time_local"] == labeled["event_time_local"] + pd.Timedelta(hours=1)
    census = leakage_census(labeled)
    census.to_csv(OUT / "leakage_counts.csv", index=False)

    published = pd.read_csv(PUBLISHED_METRICS)
    published_hist = published.loc[published["model"] == "hist_gradient_boosting"]
    metric_rows: list[dict] = []
    metric_rows.extend(score_frame("published_rows", "published", labeled, list(FEATURE_COLS)))

    for fold in DEVELOPMENT_FOLDS:
        include_test = fold.name == "2016h1"
        purged = purged_fold_frame(labeled, fold, include_test=include_test)
        metric_rows.extend(
            score_frame("purged_locked_cluster", fold.name, purged, list(FEATURE_COLS))
        )
        train_assignment = fold_assignments[fold.name]
        agreement = assignment_agreement(train_assignment, locked)
        if agreement["n_moved"] == 0:
            copied = [row for row in metric_rows if row["fold"] == fold.name and row["variant"] == "purged_locked_cluster"]
            for row in copied:
                metric_rows.append({**row, "variant": "purged_train_cluster"})
            print(f"skip {fold.name} / purged_train_cluster — same partition as the lock", flush=True)
        else:
            metric_rows.extend(
                score_frame(
                    "purged_train_cluster",
                    fold.name,
                    apply_cluster(purged, train_assignment),
                    list(FEATURE_COLS),
                )
            )
        metric_rows.extend(score_frame("purged_no_cluster", fold.name, purged, NO_CLUSTER_COLS))

    metrics = pd.DataFrame(metric_rows)
    metrics.to_csv(OUT / "fold_metrics.csv", index=False)
    report = {
        "label_hours": {
            "point": POINT_LABEL_HOURS,
            "onset_confirmation": ONSET_CONFIRM_HOURS,
            "census": list(LABEL_CENSUS_HOURS),
        },
        "target_time_matches_origin_plus_1h": int(same_clock.sum()),
        "target_time_mismatches": int((~same_clock).sum()),
        "leakage": census.to_dict(orient="records"),
        "cluster": cluster_report,
        "published_histgb": published_hist.to_dict(orient="records"),
        "metrics": metric_rows,
        "unchanged": [
            "artifacts/classification/model_lock.json",
            "artifacts/clustering/cluster_lock.json",
            "artifacts/forecasting/model_lock.json",
        ],
    }
    (OUT / "hygiene_report.json").write_text(json.dumps(_jsonable(report), indent=2), encoding="utf-8")
    print(f"wrote {OUT}", flush=True)


if __name__ == "__main__":
    main()
