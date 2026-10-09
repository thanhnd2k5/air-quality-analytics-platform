#!/usr/bin/env python3
"""Phase 9c: KMeans + Hierarchical on station profiles → lock + figures.

Requires P9b artifact:
    artifacts/clustering/station_profiles.csv

Example:
    py -3 scripts/run_clustering_phase9.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.cluster.hierarchy import dendrogram, linkage  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from src.clustering.fit import (  # noqa: E402
    FEATURE_SET_VERSION,
    PRIMARY_SEED,
    agreement_rate,
    assignment_frame,
    build_lock_payload,
    choose_lock_k,
    cluster_profile_means,
    fit_hierarchical,
    fit_kmeans,
    hierarchical_metrics,
    kmeans_metrics,
    pca_coords,
    prepare_matrix,
    seed_stability,
)

OUT = ROOT / "artifacts" / "clustering"
FIGS = OUT / "figures"
PROFILES_CSV = OUT / "station_profiles.csv"


def _save_fig(name: str) -> Path:
    FIGS.mkdir(parents=True, exist_ok=True)
    path = FIGS / name
    plt.tight_layout()
    plt.savefig(path, dpi=120)
    plt.close()
    return path


def plot_elbow(metrics: pd.DataFrame) -> Path:
    km = metrics.loc[metrics["method"] == "kmeans"].sort_values("k")
    plt.figure(figsize=(5, 3.5))
    plt.plot(km["k"], km["inertia"], marker="o")
    plt.xlabel("K")
    plt.ylabel("Inertia")
    plt.title("KMeans elbow (station profiles)")
    return _save_fig("elbow.png")


def plot_silhouette(metrics: pd.DataFrame) -> Path:
    plt.figure(figsize=(6, 3.5))
    for method, g in metrics.groupby("method"):
        g = g.sort_values("k")
        plt.plot(g["k"], g["silhouette"], marker="o", label=method)
    plt.xlabel("K")
    plt.ylabel("Silhouette")
    plt.title("Silhouette by method / K")
    plt.legend()
    return _save_fig("silhouette.png")


def plot_pca(coords, labels, names) -> Path:
    plt.figure(figsize=(7, 5))
    scatter = plt.scatter(coords[:, 0], coords[:, 1], c=labels, cmap="tab10", s=80)
    for i, name in enumerate(names):
        plt.annotate(name, (coords[i, 0], coords[i, 1]), fontsize=7, xytext=(4, 4), textcoords="offset points")
    plt.xlabel("PC1")
    plt.ylabel("PC2")
    plt.title("PCA of scaled station profiles (KMeans lock)")
    plt.colorbar(scatter, label="cluster_id")
    return _save_fig("pca_clusters.png")


def plot_dendrogram(X, names) -> Path:
    Z = linkage(X, method="ward")
    plt.figure(figsize=(9, 4.5))
    dendrogram(Z, labels=list(names), leaf_rotation=45, leaf_font_size=8)
    plt.title("Ward hierarchical dendrogram (station profiles)")
    plt.ylabel("Distance")
    return _save_fig("dendrogram.png")


def write_methodology(
    *,
    k: int,
    silhouette: float,
    stability: dict,
    hier_agreement: float,
    assignment: pd.DataFrame,
) -> Path:
    path = OUT / "clustering_methodology.md"
    stations_by_cluster = (
        assignment.groupby("cluster_id")["station_name"]
        .apply(lambda s: ", ".join(sorted(s)))
        .to_dict()
    )
    lines = [
        "# Phase 9c – Clustering methodology",
        "",
        "## Input",
        "",
        f"- Profiles: `artifacts/clustering/station_profiles.csv` (`{FEATURE_SET_VERSION}`)",
        "- Window: 2013-03-01 → 2016-12-31",
        "- Features: see `profile_feature_dictionary.md` (cluster feature columns only)",
        "- Preprocessing: `StandardScaler` (zero mean, unit variance)",
        "",
        "## Methods",
        "",
        f"- **Primary:** KMeans (`n_init=10`, `random_state={PRIMARY_SEED}`), K ∈ {{2, 3, 4}}",
        "- **Cross-check:** Agglomerative clustering (Ward) + dendrogram",
        "- **Viz:** PCA (2D) of scaled features; elbow + silhouette plots",
        "",
        "## Selection",
        "",
        f"- Locked **K = {k}** (max KMeans silhouette among grid; ties → smaller K)",
        f"- Locked silhouette = **{silhouette:.4f}**",
        f"- Seed stability (42, 0, 123): `{stability}`",
        f"- Pairwise agreement KMeans vs Ward (same K): **{hier_agreement:.4f}**",
        "",
        "## Locked assignment",
        "",
    ]
    for cid, names in sorted(stations_by_cluster.items()):
        lines.append(f"- cluster_{cid}: {names}")
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            "- `k_selection_metrics.csv`",
            "- `cluster_assignment.csv`",
            "- `cluster_profiles.csv`",
            "- `cluster_lock.json`",
            "- `figures/elbow.png`, `silhouette.png`, `pca_clusters.png`, `dendrogram.png`",
            "",
            "## Notes",
            "",
            "- Not clustering hourly fact rows.",
            "- District / lat-lon / weather not in the model (baseline in P9e).",
            "- Interpretation narrative: P9e `cluster_interpretation.md`.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    FIGS.mkdir(parents=True, exist_ok=True)

    if not PROFILES_CSV.is_file():
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": f"missing {PROFILES_CSV}",
                    "hint": "Run py -3 scripts/run_clustering_phase9b.py first",
                }
            )
        )
        return 1

    profiles = pd.read_csv(PROFILES_CSV)
    matrix = prepare_matrix(profiles)

    km_m = kmeans_metrics(matrix.X)
    hier_m = hierarchical_metrics(matrix.X)
    metrics = pd.concat([km_m, hier_m], ignore_index=True)
    metrics_path = OUT / "k_selection_metrics.csv"
    metrics.to_csv(metrics_path, index=False)

    k = choose_lock_k(metrics)
    labels_km = fit_kmeans(matrix.X, k, random_state=PRIMARY_SEED)
    labels_hier = fit_hierarchical(matrix.X, k)
    stability = seed_stability(matrix.X, k)
    hier_agree = agreement_rate(labels_km, labels_hier)

    assignment = assignment_frame(matrix, labels_km, method="kmeans", k=k)
    assignment_path = OUT / "cluster_assignment.csv"
    assignment.to_csv(assignment_path, index=False)

    profiles_by_cluster = cluster_profile_means(profiles, assignment)
    profiles_path = OUT / "cluster_profiles.csv"
    profiles_by_cluster.to_csv(profiles_path, index=False)

    lock = build_lock_payload(
        k=k,
        method="kmeans",
        metrics=metrics,
        assignment=assignment,
        stability=stability,
        hier_agreement=hier_agree,
        feature_cols=matrix.feature_cols,
    )
    lock_path = OUT / "cluster_lock.json"
    lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")

    plot_elbow(metrics)
    plot_silhouette(metrics)
    coords = pca_coords(matrix.X)
    plot_pca(coords, assignment["cluster_id"].to_numpy(), matrix.names)
    plot_dendrogram(matrix.X, matrix.names)
    write_methodology(
        k=k,
        silhouette=float(lock["silhouette"]),
        stability=stability,
        hier_agreement=hier_agree,
        assignment=assignment,
    )

    summary = {
        "ok": True,
        "phase": "P9c",
        "k": k,
        "method": "kmeans",
        "silhouette": lock["silhouette"],
        "hierarchical_pairwise_agreement": hier_agree,
        "seed_stability": stability,
        "lock": str(lock_path),
        "assignment": str(assignment_path),
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
