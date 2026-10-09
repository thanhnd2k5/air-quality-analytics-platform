# Phase 9c – Clustering methodology

## Input

- Profiles: `artifacts/clustering/station_profiles.csv` (`v1_1_1_label_by_pm25`)
- Window: 2013-03-01 → 2016-12-31
- Features: see `profile_feature_dictionary.md` (cluster feature columns only)
- Preprocessing: `StandardScaler` (zero mean, unit variance)

## Methods

- **Primary:** KMeans (`n_init=10`, `random_state=42`), K ∈ {2, 3, 4}
- **Cross-check:** Agglomerative clustering (Ward) + dendrogram
- **Viz:** PCA (2D) of scaled features; elbow + silhouette plots

## Selection

- Locked **K = 2** (max KMeans silhouette among grid; ties → smaller K)
- Locked silhouette = **0.6634**
- Seed stability (42, 0, 123): `{'k': 2, 'seeds': [42, 0, 123], 'all_match_primary_seed': True, 'n_matching_primary': 3, 'n_seeds': 3}`
- Pairwise agreement KMeans vs Ward (same K): **1.0000**

## Locked assignment

- `elevated_core` (id 0): Aotizhongxin, Dongsi, Guanyuan, Gucheng, Nongzhanguan, Shunyi, Tiantan, Wanliu, Wanshouxigong
- `cleaner_outskirts` (id 1): Changping, Dingling, Huairou

## Artifacts

- `k_selection_metrics.csv`
- `cluster_assignment.csv`
- `cluster_profiles.csv`
- `cluster_lock.json`
- `figures/elbow.png`, `silhouette.png`, `pca_clusters.png`, `dendrogram.png`
- seed sync: `dbt/.../seeds/station_cluster_assignment.csv`, `data/clustering/station_cluster_assignment.csv`

## Notes

- Not clustering hourly fact rows.
- District / lat-lon / weather not in the model (baseline in P9e).
- Cluster ids remapped by descending mean_pm25 (0 = elevated).
- Interpretation narrative: P9e `cluster_interpretation.md`.
