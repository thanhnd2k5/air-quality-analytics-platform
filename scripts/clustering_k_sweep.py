#!/usr/bin/env python3
"""Silhouette over every K the 12 station profiles allow (2 … n−1), for the dashboard chart.

Display only: the lock was chosen on K ∈ {2, 3, 4} (src/clustering/fit.py DEFAULT_K_GRID) and is
not rewritten here. The script checks that the shared K values reproduce k_selection_metrics.csv
and reports whether the locked K is still the best silhouette on the wider range.

Output: artifacts/clustering/k_selection_extended.csv (same columns as k_selection_metrics.csv)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.clustering.fit import hierarchical_metrics, kmeans_metrics, prepare_matrix  # noqa: E402

OUT = ROOT / "artifacts" / "clustering"


def main() -> int:
    profiles = pd.read_csv(OUT / "station_profiles.csv")
    matrix = prepare_matrix(profiles)
    grid = tuple(range(2, len(matrix.X)))  # silhouette needs 2 ≤ K ≤ n − 1
    sweep = pd.concat([kmeans_metrics(matrix.X, grid), hierarchical_metrics(matrix.X, grid)], ignore_index=True)

    locked = pd.read_csv(OUT / "k_selection_metrics.csv")
    merged = locked.merge(sweep, on=["method", "k"], suffixes=("_locked", "_sweep"))
    drift = float((merged["silhouette_locked"] - merged["silhouette_sweep"]).abs().max())
    if drift > 1e-9:
        print(json.dumps({"ok": False, "error": f"sweep differs from k_selection_metrics.csv by {drift}"}))
        return 1

    lock_k = int(json.loads((OUT / "cluster_lock.json").read_text(encoding="utf-8"))["k"])
    km = sweep[sweep["method"] == "kmeans"]
    best_k = int(km.loc[km["silhouette"].idxmax(), "k"])
    path = OUT / "k_selection_extended.csv"
    sweep.to_csv(path, index=False)
    print(json.dumps({"ok": True, "k_range": [grid[0], grid[-1]], "lock_k": lock_k, "best_k_on_range": best_k,
                      "output": str(path.relative_to(ROOT))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
