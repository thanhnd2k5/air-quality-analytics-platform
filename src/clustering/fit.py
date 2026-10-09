"""Phase 9c: scale station profiles, KMeans + Hierarchical, lock selection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from src.clustering.profiles import CLUSTER_FEATURE_COLS, META_COLS
from src.clustering.smoke import PROFILE_END, PROFILE_START

FEATURE_SET_VERSION = "v1_pollutant_season_episode"
DEFAULT_K_GRID = (2, 3, 4)
DEFAULT_SEEDS = (42, 0, 123)
PRIMARY_SEED = 42


@dataclass(frozen=True)
class ScaledMatrix:
    names: pd.Series
    keys: pd.Series
    districts: pd.Series
    feature_cols: list[str]
    X_raw: np.ndarray
    X: np.ndarray
    scaler: StandardScaler


def prepare_matrix(profiles: pd.DataFrame) -> ScaledMatrix:
    missing = [c for c in CLUSTER_FEATURE_COLS if c not in profiles.columns]
    if missing:
        raise ValueError(f"profiles missing columns: {missing}")
    feature_cols = list(CLUSTER_FEATURE_COLS)
    X_raw = profiles[feature_cols].astype(float).to_numpy()
    if np.isnan(X_raw).any():
        raise ValueError("profiles contain NaN in cluster features")
    scaler = StandardScaler()
    X = scaler.fit_transform(X_raw)
    return ScaledMatrix(
        names=profiles["station_name"].astype(str),
        keys=profiles["station_key"],
        districts=profiles["district"].astype(str),
        feature_cols=feature_cols,
        X_raw=X_raw,
        X=X,
        scaler=scaler,
    )


def kmeans_metrics(
    X: np.ndarray,
    k_grid: tuple[int, ...] = DEFAULT_K_GRID,
    *,
    random_state: int = PRIMARY_SEED,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for k in k_grid:
        model = KMeans(n_clusters=k, n_init=10, random_state=random_state)
        labels = model.fit_predict(X)
        sil = float(silhouette_score(X, labels)) if k < len(X) else float("nan")
        rows.append(
            {
                "method": "kmeans",
                "k": k,
                "random_state": random_state,
                "inertia": float(model.inertia_),
                "silhouette": sil,
            }
        )
    return pd.DataFrame(rows)


def hierarchical_metrics(
    X: np.ndarray,
    k_grid: tuple[int, ...] = DEFAULT_K_GRID,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for k in k_grid:
        model = AgglomerativeClustering(n_clusters=k, linkage="ward")
        labels = model.fit_predict(X)
        sil = float(silhouette_score(X, labels)) if k < len(X) else float("nan")
        rows.append(
            {
                "method": "agglomerative_ward",
                "k": k,
                "random_state": None,
                "inertia": None,
                "silhouette": sil,
            }
        )
    return pd.DataFrame(rows)


def fit_kmeans(X: np.ndarray, k: int, *, random_state: int = PRIMARY_SEED) -> np.ndarray:
    return KMeans(n_clusters=k, n_init=10, random_state=random_state).fit_predict(X)


def fit_hierarchical(X: np.ndarray, k: int) -> np.ndarray:
    return AgglomerativeClustering(n_clusters=k, linkage="ward").fit_predict(X)


def _label_signature(labels: np.ndarray) -> frozenset[frozenset[int]]:
    """Partition signature invariant to cluster id permutation."""
    groups: dict[int, set[int]] = {}
    for i, lab in enumerate(labels.tolist()):
        groups.setdefault(int(lab), set()).add(i)
    return frozenset(frozenset(v) for v in groups.values())


def seed_stability(
    X: np.ndarray,
    k: int,
    seeds: tuple[int, ...] = DEFAULT_SEEDS,
) -> dict[str, Any]:
    sigs = [_label_signature(fit_kmeans(X, k, random_state=s)) for s in seeds]
    primary = sigs[0]
    matches = sum(1 for s in sigs if s == primary)
    return {
        "k": k,
        "seeds": list(seeds),
        "all_match_primary_seed": matches == len(seeds),
        "n_matching_primary": matches,
        "n_seeds": len(seeds),
    }


def agreement_rate(labels_a: np.ndarray, labels_b: np.ndarray) -> float:
    """Fraction of stations in the same pairwise co-membership relation."""
    n = len(labels_a)
    if n < 2:
        return 1.0
    same = 0
    total = 0
    for i in range(n):
        for j in range(i + 1, n):
            total += 1
            same_a = labels_a[i] == labels_a[j]
            same_b = labels_b[i] == labels_b[j]
            if same_a == same_b:
                same += 1
    return same / total


def choose_lock_k(metrics: pd.DataFrame) -> int:
    """Prefer silhouette among KMeans rows; ties → smaller k (more interpretable)."""
    km = metrics.loc[metrics["method"] == "kmeans"].copy()
    if km.empty:
        raise ValueError("no kmeans metrics")
    km = km.sort_values(["silhouette", "k"], ascending=[False, True])
    return int(km.iloc[0]["k"])


def remapped_labels_by_size(labels: np.ndarray) -> np.ndarray:
    """Remap cluster ids so 0 = largest cluster, then descending size."""
    labels = np.asarray(labels)
    counts = pd.Series(labels).value_counts()
    order = list(counts.index)
    mapping = {old: new for new, old in enumerate(order)}
    return np.array([mapping[int(x)] for x in labels], dtype=int)


def cluster_labels_readable(k: int) -> dict[int, str]:
    """Semantic labels for locked K=2; generic fallback otherwise."""
    if k == 2:
        # Remapped by size: 0 = larger elevated group, 1 = smaller cleaner group
        return {0: "elevated_core", 1: "cleaner_outskirts"}
    return {i: f"cluster_{i}" for i in range(k)}


def assignment_frame(
    matrix: ScaledMatrix,
    labels: np.ndarray,
    *,
    method: str,
    k: int,
) -> pd.DataFrame:
    labels = remapped_labels_by_size(labels)
    readable = cluster_labels_readable(k)
    return pd.DataFrame(
        {
            "station_key": matrix.keys.values,
            "station_name": matrix.names.values,
            "district": matrix.districts.values,
            "cluster_id": labels,
            "cluster_label": [readable[int(x)] for x in labels],
            "method": method,
            "k": k,
            "feature_set_version": FEATURE_SET_VERSION,
        }
    )


def cluster_profile_means(
    profiles: pd.DataFrame,
    assignment: pd.DataFrame,
) -> pd.DataFrame:
    merged = profiles.merge(
        assignment[["station_key", "cluster_id", "cluster_label"]],
        on="station_key",
        how="inner",
    )
    cols = [c for c in CLUSTER_FEATURE_COLS if c in merged.columns]
    g = merged.groupby(["cluster_id", "cluster_label"], as_index=False)[cols].mean()
    counts = merged.groupby("cluster_id").size().rename("n_stations").reset_index()
    g = g.merge(counts, on="cluster_id")
    return g.sort_values("cluster_id")


def pca_coords(X: np.ndarray, n_components: int = 2) -> np.ndarray:
    return PCA(n_components=n_components, random_state=PRIMARY_SEED).fit_transform(X)


def build_lock_payload(
    *,
    k: int,
    method: str,
    metrics: pd.DataFrame,
    assignment: pd.DataFrame,
    stability: dict[str, Any],
    hier_agreement: float,
    feature_cols: list[str],
) -> dict[str, Any]:
    km = metrics.loc[(metrics["method"] == "kmeans") & (metrics["k"] == k)].iloc[0]
    return {
        "phase": "P9c",
        "locked_at": datetime.now(timezone.utc).isoformat(),
        "method": method,
        "k": k,
        "random_state": PRIMARY_SEED,
        "n_init": 10,
        "feature_set_version": FEATURE_SET_VERSION,
        "feature_cols": feature_cols,
        "profile_window": {"start": PROFILE_START, "end": PROFILE_END},
        "silhouette": float(km["silhouette"]),
        "inertia": float(km["inertia"]),
        "seed_stability": stability,
        "hierarchical_pairwise_agreement": hier_agreement,
        "meta_cols_excluded_from_model": list(META_COLS),
        "assignment": assignment[
            ["station_key", "station_name", "cluster_id", "cluster_label"]
        ].to_dict(orient="records"),
        "selection_notes": (
            "K chosen by max KMeans silhouette among {2,3,4}; "
            "ties prefer smaller K. Primary method KMeans; Ward hierarchical for cross-check."
        ),
    }
