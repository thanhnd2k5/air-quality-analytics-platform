# Phase 8 – EDA notebooks

Read from PostgreSQL DWH / marts (`dwh.fact_air_quality_hourly`, dims, existing marts).  
Do **not** rebuild final analysis from raw UCI CSV.

## Batch runner (recommended evidence path)

From repo root (Postgres up, `.env` set):

```bash
py -3 scripts/smoke_dwh_fact.py
py -3 scripts/run_eda_phase8b.py
```

Writes CSV/PNG + `artifacts/eda/eda_findings.md` and `eda_summary.json`.

## Notebooks

| Notebook | Focus |
|----------|--------|
| `01_temporal.ipynb` | Hourly / daily / monthly / seasonal |
| `02_station.ipynb` | Mean / median / variance / peaks / ranking |
| `03_pollutant.ipynb` | PM2.5, PM10, SO₂, NO₂, CO, O₃ |
| `04_weather.ipynb` | Weather vs PM2.5 (pattern only) |
| `05_episodes_sensitivity.ipynb` | *(P8c)* Threshold / min_hours / K grid |
| `06_episodes_analysis.ipynb` | *(P8c)* Per-station, multi-station, weather-in-episode |

Helpers live in `src/eda/analysis.py`. Regenerate notebook stubs: `py -3 scripts/_write_eda_notebooks.py`.

## Connection smoke

```bash
py -3 scripts/smoke_dwh_fact.py
```
