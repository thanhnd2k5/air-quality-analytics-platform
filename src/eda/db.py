"""Read-only Postgres helpers for EDA notebooks and smoke scripts.

Uses the same env vars as staging/dbt (`POSTGRES_*` from `.env`).
Does not write to staging / dwh / mart.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Sequence

import pandas as pd
from psycopg2.extensions import connection as PgConnection

from src.staging.load import connect


@contextmanager
def dwh_connection() -> Iterator[PgConnection]:
    """Open a warehouse connection and close it when the block ends."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def fetch_dicts(
    sql: str,
    params: Sequence[Any] | dict[str, Any] | None = None,
    *,
    conn: PgConnection | None = None,
) -> list[dict[str, Any]]:
    """Run a SELECT and return a list of row dicts."""

    def _run(active: PgConnection) -> list[dict[str, Any]]:
        with active.cursor() as cur:
            cur.execute(sql, params)
            if cur.description is None:
                return []
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    if conn is not None:
        return _run(conn)

    with dwh_connection() as owned:
        return _run(owned)


def read_sql(
    sql: str,
    params: Sequence[Any] | dict[str, Any] | None = None,
    *,
    conn: PgConnection | None = None,
) -> pd.DataFrame:
    """Run a SELECT and return a DataFrame (psycopg2 cursor → pandas, no SQLAlchemy)."""
    rows = fetch_dicts(sql, params, conn=conn)
    return pd.DataFrame(rows)


def smoke_fact_air_quality() -> dict[str, Any]:
    """Minimal Phase 8 gate: fact row count and time span."""
    sql = """
        select
            count(*)::bigint as row_count,
            count(distinct station_key)::int as station_count,
            min(event_time_local) as min_event_time,
            max(event_time_local) as max_event_time,
            count(pm25_ug_m3)::bigint as pm25_non_null
        from dwh.fact_air_quality_hourly
    """
    rows = fetch_dicts(sql)
    row = rows[0] if rows else {}
    expected_rows = 420_768
    expected_stations = 12
    ok = (
        row.get("row_count") == expected_rows
        and row.get("station_count") == expected_stations
        and row.get("min_event_time") is not None
        and row.get("max_event_time") is not None
    )
    return {
        "ok": ok,
        "expected_row_count": expected_rows,
        "expected_station_count": expected_stations,
        **{k: (v.isoformat(sep=" ") if hasattr(v, "isoformat") else v) for k, v in row.items()},
    }
