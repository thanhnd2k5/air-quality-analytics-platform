#!/usr/bin/env python3
"""Run a few OLAP checks against the Phase 7 warehouse and write a JSON artifact."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from src.staging.load import connect  # noqa: E402


def _rows(cur) -> list[dict]:
    columns = [desc[0] for desc in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def main() -> int:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                select station.station_name, calendar.year, calendar.month,
                       round(avg(fact.pm25_ug_m3)::numeric, 2) as pm25_avg
                from dwh.fact_air_quality_hourly as fact
                join dwh.dim_station as station on fact.station_key = station.station_key
                join dwh.dim_date as calendar on fact.date_key = calendar.date_key
                group by 1, 2, 3
                order by pm25_avg desc nulls last
                limit 5
                """
            )
            top_months = _rows(cur)
            cur.execute(
                """
                select calendar.season,
                       round(avg(fact.pm25_ug_m3)::numeric, 2) as pm25_avg,
                       count(*) as hour_count
                from dwh.fact_air_quality_hourly as fact
                join dwh.dim_date as calendar on fact.date_key = calendar.date_key
                group by 1
                order by 1
                """
            )
            by_season = _rows(cur)
            cur.execute(
                """
                select width_bucket(temperature_c, -20, 40, 6) as temp_bin,
                       round(avg(pm25_ug_m3)::numeric, 2) as pm25_avg,
                       count(*) as hour_count
                from dwh.fact_air_quality_hourly
                where temperature_c is not null and pm25_ug_m3 is not null
                group by 1
                order by 1
                """
            )
            by_temp = _rows(cur)
    finally:
        conn.close()

    report = {
        "top_station_months_by_pm25": top_months,
        "pm25_by_season": by_season,
        "pm25_by_temperature_bin": by_temp,
    }
    for row in top_months + by_season + by_temp:
        for key, value in list(row.items()):
            if hasattr(value, "as_tuple"):
                row[key] = float(value)
    out = ROOT / "artifacts" / "dwh" / "olap_checks.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    seasons = {row["season"] for row in by_season}
    ok = len(top_months) == 5 and seasons == {"winter", "spring", "summer", "autumn"} and len(by_temp) > 1
    print(json.dumps({"output": str(out), "ok": ok, "seasons": sorted(seasons)}))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
