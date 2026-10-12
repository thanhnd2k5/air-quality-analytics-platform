#!/usr/bin/env python3
"""OLAP evidence for the warehouse.

1. Runs every named query in sql/olap/olap_operations.sql (roll-up, drill-down, slice,
   dice, pivot, ROLLUP / CUBE / GROUPING SETS) and stores a preview of each result.
2. Verifies every pre-computed cuboid cell against a fresh aggregation of the fact
   (mart_station_daily, mart_station_monthly, the 32 cuboids of mart_olap_cube) and the
   lattice property monthly = roll-up of daily.
3. Checks that drill-down levels add back up to their parent.

Writes artifacts/dwh/olap_checks.json. Exit code 0 only when every cell matches.

Example:
    python scripts/run_olap_checks.py
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from src.eda.db import dwh_connection, fetch_dicts  # noqa: E402
from src.olap.queries import load_queries, run_query  # noqa: E402

OUT = ROOT / "artifacts" / "dwh" / "olap_checks.json"

# Relative tolerance for float sums (avg × count round-trips).
TOL = "1e-6 * greatest(1, abs(coalesce(f.ps, 0)))"

CUBOID_CHECKS = {
    "mart_station_daily (station × day)": f"""
        with fresh as (
            select station_key, date_key,
                   count(*) as hc, count(pm25_ug_m3) as pc, sum(pm25_ug_m3) as ps
            from dwh.fact_air_quality_hourly
            group by station_key, date_key
        )
        select count(*) as cells,
               count(*) filter (
                   where m.station_key is not null and f.station_key is not null
                     and m.hour_count = f.hc and m.pm25_hour_count = f.pc
                     and abs(coalesce(m.pm25_ug_m3_avg * m.pm25_hour_count, 0) - coalesce(f.ps, 0)) <= {TOL}
               ) as matched
        from mart.mart_station_daily as m
        full join fresh as f on m.station_key = f.station_key and m.date_key = f.date_key
    """,
    "mart_station_monthly (station × month)": f"""
        with fresh as (
            select fact.station_key, calendar.year, calendar.month,
                   count(*) as hc, count(fact.pm25_ug_m3) as pc, sum(fact.pm25_ug_m3) as ps
            from dwh.fact_air_quality_hourly as fact
            join dwh.dim_date as calendar on fact.date_key = calendar.date_key
            group by fact.station_key, calendar.year, calendar.month
        )
        select count(*) as cells,
               count(*) filter (
                   where m.station_key is not null and f.station_key is not null
                     and m.hour_count = f.hc and m.pm25_hour_count = f.pc
                     and abs(coalesce(m.pm25_ug_m3_avg * m.pm25_hour_count, 0) - coalesce(f.ps, 0)) <= {TOL}
               ) as matched
        from mart.mart_station_monthly as m
        full join fresh as f
            on m.station_key = f.station_key and m.year = f.year and m.month = f.month
    """,
    "lattice: monthly = roll-up(daily)": f"""
        with f as (
            select station_key, year, month,
                   sum(hour_count) as hc, sum(pm25_hour_count) as pc,
                   sum(pm25_ug_m3_avg * pm25_hour_count) as ps
            from mart.mart_station_daily
            group by station_key, year, month
        )
        select count(*) as cells,
               count(*) filter (
                   where m.station_key is not null and f.station_key is not null
                     and m.hour_count = f.hc and m.pm25_hour_count = f.pc
                     and abs(coalesce(m.pm25_ug_m3_avg * m.pm25_hour_count, 0) - coalesce(f.ps, 0)) <= {TOL}
               ) as matched
        from mart.mart_station_monthly as m
        full join f on m.station_key = f.station_key and m.year = f.year and m.month = f.month
    """,
}

CUBE_CHECK = f"""
    with fresh as (
        select grouping(calendar.year, calendar.season, station.district, tod.day_part, wind.wind_quadrant) as gid,
               calendar.year, calendar.season, station.district, tod.day_part, wind.wind_quadrant,
               count(*) as hc, count(fact.pm25_ug_m3) as pc, sum(fact.pm25_ug_m3) as ps
        from dwh.fact_air_quality_hourly as fact
        join dwh.dim_date as calendar on fact.date_key = calendar.date_key
        join dwh.dim_station as station on fact.station_key = station.station_key
        join dwh.dim_time as tod on fact.time_key = tod.time_key
        join dwh.dim_wind_direction as wind on fact.wind_direction_key = wind.wind_direction_key
        group by cube (calendar.year, calendar.season, station.district, tod.day_part, wind.wind_quadrant)
    )
    select coalesce(m.grouping_id, f.gid) as grouping_id,
           max(m.cuboid) as cuboid,
           count(*) as cells,
           count(*) filter (
               where m.grouping_id is not null and f.gid is not null
                 and m.hour_count = f.hc and m.pm25_hour_count = f.pc
                 and abs(coalesce(m.pm25_sum, 0) - coalesce(f.ps, 0)) <= {TOL}
           ) as matched
    from mart.mart_olap_cube as m
    full join fresh as f
        on m.grouping_id = f.gid
       and m.year is not distinct from f.year
       and m.season is not distinct from f.season
       and m.district is not distinct from f.district
       and m.day_part is not distinct from f.day_part
       and m.wind_quadrant is not distinct from f.wind_quadrant
    group by 1
    order by 1
"""


def _jsonable(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _preview(df, n: int = 8) -> list[dict]:
    return [{k: _jsonable(v) for k, v in row.items()} for row in df.head(n).to_dict("records")]


def _drilldown_consistency(results: dict) -> list[dict]:
    """Children of a drill-down must add back to the parent (exceed_hours is distributive)."""
    year = {int(r["year"]): r for r in results["drilldown_year"].to_dict("records")}
    quarter = results["drilldown_quarter"]
    month = results["drilldown_month"]
    q4 = quarter.loc[quarter["quarter"] == 4, "exceed_hours"].sum()
    return [
        {
            "check": "Σ quarters(2015).exceed_hours = year 2015",
            "ok": int(quarter["exceed_hours"].sum()) == int(year[2015]["exceed_hours"]),
        },
        {
            "check": "Σ months(Q4/2015).exceed_hours = Q4/2015",
            "ok": int(month["exceed_hours"].sum()) == int(q4),
        },
    ]


def main() -> int:
    queries = load_queries()
    operations = []
    results = {}
    with dwh_connection() as conn:
        for name, q in queries.items():
            df = run_query(name, queries, conn=conn)
            results[name] = df
            operations.append(
                {"name": name, "op": q.op, "desc": q.desc, "rows": int(len(df)), "preview": _preview(df)}
            )

        cuboids = []
        for label, sql in CUBOID_CHECKS.items():
            row = fetch_dicts(sql, conn=conn)[0]
            cuboids.append({"cuboid": label, "cells": int(row["cells"]), "matched": int(row["matched"])})
        cube_rows = fetch_dicts(CUBE_CHECK, conn=conn)
        for row in cube_rows:
            cuboids.append(
                {
                    "cuboid": f"mart_olap_cube [{row['cuboid']}]",
                    "cells": int(row["cells"]),
                    "matched": int(row["matched"]),
                }
            )

    for c in cuboids:
        c["pct_correct"] = round(100.0 * c["matched"] / c["cells"], 3) if c["cells"] else 0.0
    total_cells = sum(c["cells"] for c in cuboids)
    total_matched = sum(c["matched"] for c in cuboids)
    fully_correct = sum(1 for c in cuboids if c["matched"] == c["cells"])
    drill = _drilldown_consistency(results)

    ops_present = sorted({tok for o in operations if (tok := o["op"].split(" ")[0]).isupper()})
    required = {"ROLL-UP", "DRILL-DOWN", "SLICE", "DICE", "PIVOT"}
    ok = (
        total_cells > 0
        and total_matched == total_cells
        and len(cube_rows) == 32
        and all(d["ok"] for d in drill)
        and required.issubset(ops_present)
    )
    report = {
        "ok": ok,
        "required_operations": sorted(required),
        "operations_present": ops_present,
        "operations": operations,
        "cuboid_checks": cuboids,
        "cube_cuboid_count": len(cube_rows),
        "summary": {
            "cuboids_checked": len(cuboids),
            "cuboids_fully_correct": fully_correct,
            "cells_checked": total_cells,
            "cells_matched": total_matched,
            "pct_cells_correct": round(100.0 * total_matched / total_cells, 3) if total_cells else 0.0,
        },
        "drilldown_consistency": drill,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), "ok": ok, **report["summary"]}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
