# Reusable clustering SQL (Phase 9)

Read-only against `dwh` / `mart`. Grain for clustering is **one row per station** (station profile), not hourly fact rows.

## Profile window

- `2013-03-01 00:00:00` → `2016-12-31 23:00:00` (exclude partial 2017)

## Starter files

- `smoke_clustering_window.sql` — P9a gate (fact span + station count in window)
- `station_pollution_profile.sql` — P9b one-row-per-station pollution profile

## Python

- `scripts/run_clustering_phase9b.py` → `artifacts/clustering/station_profiles.csv` + `profile_qc.json`
- Feature dictionary: `artifacts/clustering/profile_feature_dictionary.md`
