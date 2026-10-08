# Phase 8 – EDA notebooks

Read from PostgreSQL DWH / marts (`dwh.fact_air_quality_hourly`, dims, existing marts).  
Do **not** rebuild final analysis from raw UCI CSV.

## Planned notebooks (P8b+)

| Notebook | Focus |
|----------|--------|
| `01_temporal.ipynb` | Hourly / daily / monthly / seasonal |
| `02_station.ipynb` | Mean / median / variance / peaks / ranking |
| `03_pollutant.ipynb` | PM2.5, PM10, SO₂, NO₂, CO, O₃ |
| `04_weather.ipynb` | Weather vs PM2.5 (pattern only) |
| `05_episodes_sensitivity.ipynb` | Threshold / min_hours / K grid → lock definition |
| `06_episodes_analysis.ipynb` | Per-station, multi-station, weather-in-episode |

## Connection

From repo root, with `.env` loaded (`POSTGRES_HOST` / `POSTGRES_PORT`, usually `localhost:5433`):

```python
from src.eda.db import read_sql, dwh_connection

df = read_sql("select count(*) as n from dwh.fact_air_quality_hourly")
```

Smoke gate (P8-01):

```bash
python scripts/smoke_dwh_fact.py
```
