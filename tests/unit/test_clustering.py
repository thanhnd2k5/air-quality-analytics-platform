"""Unit tests for Phase 9 clustering helpers (no database)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.clustering.fit import (
    agreement_rate,
    assignment_frame,
    choose_lock_k,
    cluster_labels_readable,
    prepare_matrix,
    remapped_labels_by_mean,
    seed_stability,
)
from src.clustering.profiles import CLUSTER_FEATURE_COLS, META_COLS, load_profile_sql
from src.clustering.smoke import PROFILE_END, PROFILE_START


def _toy_profiles() -> pd.DataFrame:
    """12 synthetic stations with clear high/low PM2.5 split."""
    rows = []
    for i in range(9):
        rows.append(_station_row(i + 1, f"High{i}", mean_pm25=80.0 + i))
    for i in range(3):
        rows.append(_station_row(100 + i, f"Low{i}", mean_pm25=50.0 + i))
    return pd.DataFrame(rows)


def _station_row(key: int, name: str, *, mean_pm25: float) -> dict:
    base = {c: 0.0 for c in CLUSTER_FEATURE_COLS}
    base.update(
        {
            "station_key": key,
            "station_name": name,
            "district": "X",
            "hour_count": 1000,
            "pm25_hour_count": 1000,
            "mean_pm25": mean_pm25,
            "median_pm25": mean_pm25 - 5,
            "std_pm25": 10.0,
            "pct_hours_pm25_ge_75": mean_pm25 / 2,
            "pct_hours_pm25_ge_115": mean_pm25 / 4,
            "episode_count": mean_pm25,
            "mean_episode_duration_h": 10.0,
            "total_episode_hours": mean_pm25 * 10,
        }
    )
    return base


def test_choose_lock_k_prefers_higher_silhouette_then_smaller_k():
    metrics = pd.DataFrame(
        [
            {"method": "kmeans", "k": 2, "silhouette": 0.5},
            {"method": "kmeans", "k": 3, "silhouette": 0.6},
            {"method": "kmeans", "k": 4, "silhouette": 0.6},
            {"method": "agglomerative_ward", "k": 2, "silhouette": 0.9},
        ]
    )
    # Max sil=0.6 among kmeans; tie → smaller k → 3
    assert choose_lock_k(metrics) == 3


def test_remapped_labels_by_mean_puts_high_pollution_as_zero():
    # Raw KMeans ids flipped vs pollution: lab 0 = clean, lab 1 = dirty
    labels = np.array([0, 0, 1, 1, 1])
    mean_pm25 = np.array([40.0, 45.0, 90.0, 95.0, 100.0])
    remapped = remapped_labels_by_mean(labels, mean_pm25)
    assert remapped.tolist() == [1, 1, 0, 0, 0]
    assert cluster_labels_readable(2)[0] == "elevated_core"
    assert cluster_labels_readable(2)[1] == "cleaner_outskirts"


def test_remapped_labels_by_mean_not_by_size():
    # Cleaner group larger — size remap would wrongly put clean as 0
    labels = np.array([0, 0, 0, 1, 1])  # 0 large, 1 small
    mean_pm25 = np.array([40.0, 42.0, 41.0, 100.0, 110.0])
    remapped = remapped_labels_by_mean(labels, mean_pm25)
    assert remapped.tolist() == [1, 1, 1, 0, 0]


def test_agreement_rate_identical_and_complement():
    a = np.array([0, 0, 1, 1])
    assert agreement_rate(a, a) == pytest.approx(1.0)
    # Completely swapped ids but same partition → still 1.0 pairwise
    b = np.array([1, 1, 0, 0])
    assert agreement_rate(a, b) == pytest.approx(1.0)
    # Different partition
    c = np.array([0, 1, 0, 1])
    assert agreement_rate(a, c) < 1.0


def test_seed_stability_and_assignment_frame_on_toy():
    profiles = _toy_profiles()
    # Align column order expected by prepare_matrix
    profiles = profiles[list(META_COLS) + list(CLUSTER_FEATURE_COLS)]
    matrix = prepare_matrix(profiles)
    stability = seed_stability(matrix.X, k=2)
    assert stability["all_match_primary_seed"] is True

    from src.clustering.fit import fit_kmeans

    labels = fit_kmeans(matrix.X, 2)
    assignment = assignment_frame(
        matrix,
        labels,
        method="kmeans",
        k=2,
        mean_pm25=profiles["mean_pm25"].to_numpy(),
    )
    elevated = assignment.loc[assignment["cluster_id"] == 0]
    cleaner = assignment.loc[assignment["cluster_id"] == 1]
    assert (elevated["cluster_label"] == "elevated_core").all()
    assert (cleaner["cluster_label"] == "cleaner_outskirts").all()
    assert elevated["station_name"].str.startswith("High").all()
    assert cleaner["station_name"].str.startswith("Low").all()
    merged = profiles.merge(assignment[["station_key", "cluster_id"]], on="station_key")
    mean_by_c = merged.groupby("cluster_id")["mean_pm25"].mean()
    assert float(mean_by_c[0]) > float(mean_by_c[1])


def test_load_profile_sql_injects_window_bounds():
    sql = load_profile_sql()
    assert "__PROFILE_START__" not in sql
    assert "__PROFILE_END__" not in sql
    assert PROFILE_START in sql
    assert PROFILE_END in sql
    assert "timestamp '" in sql
