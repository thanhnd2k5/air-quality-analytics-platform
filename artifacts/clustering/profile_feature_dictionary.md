# Phase 9b – Station profile feature dictionary

Grain: **one row per station** (`station_key`).  
Source SQL: `sql/clustering/station_pollution_profile.sql`  
Window: **2013-03-01 00:00 → 2016-12-31 23:00** (exclude partial 2017).  
Export: `artifacts/clustering/station_profiles.csv`

Season labels come from `dwh.dim_date.season` (same as Phase 8):  
`winter` = Dec–Feb, `spring` = Mar–May, `summer` = Jun–Aug, `autumn` = Sep–Nov.

## Meta columns (not used in KMeans v1)

| Column | Description |
|--------|-------------|
| `station_key` | Warehouse station id |
| `station_name` | Display name |
| `district` | Administrative district (baseline vs cluster only) |
| `hour_count` | Calendar hours in window |
| `pm25_hour_count` | Hours with non-null PM2.5 |

## Cluster feature columns (StandardScaler → KMeans / Hierarchical)

| Column | Description |
|--------|-------------|
| `mean_pm25` | Mean PM2.5 (µg/m³), non-null hours |
| `median_pm25` | Median PM2.5 |
| `std_pm25` | Sample stdev of PM2.5 |
| `mean_pm10` | Mean PM10 |
| `mean_no2` | Mean NO₂ |
| `mean_co` | Mean CO |
| `mean_so2` | Mean SO₂ |
| `mean_o3` | Mean O₃ |
| `mean_pm25_spring` | Mean PM2.5 in spring hours |
| `mean_pm25_summer` | Mean PM2.5 in summer hours |
| `mean_pm25_autumn` | Mean PM2.5 in autumn hours |
| `mean_pm25_winter` | Mean PM2.5 in winter hours |
| `pct_hours_pm25_ge_75` | % of non-null PM2.5 hours ≥ 75 |
| `pct_hours_pm25_ge_115` | % of non-null PM2.5 hours ≥ 115 (episode dirty threshold) |
| `episode_count` | Episodes overlapping the window (`mart.mart_pm25_episodes`) |
| `mean_episode_duration_h` | Mean **clipped** duration (hours inside window only); `0` if none |
| `total_episode_hours` | Sum of clipped episode hours inside the window |

Feature-set version: `v1_1_1_label_by_pm25` (episode overlap + clip; cluster ids by mean_pm25).

## Explicitly excluded from KMeans v1

- `latitude` / `longitude` / `district` (geography baseline)
- Station weather means (temp, RH, wind)

## QC

`scripts/run_clustering_phase9b.py` writes `profile_qc.json`: 12 unique stations, no nulls on cluster features, soft ranking Dongsi highest / Dingling lowest mean PM2.5.
