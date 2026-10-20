"""SQLite client for simulated operational DB (watermark CDC extract).

Phase 2 of docs/OPERATIONAL_DB_INGESTION_DESIGN.md.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[2]
_REPO_DB_PATH = ROOT / "data" / "raw" / "database" / "prsa_operational.db"


def default_db_path() -> Path:
    """Prefer OPERATIONAL_DB_PATH env (Airflow); else repo-relative file."""
    return Path(os.getenv("OPERATIONAL_DB_PATH") or _REPO_DB_PATH)


# Back-compat alias for CLI defaults (resolved at import for local runs).
DEFAULT_DB_PATH = default_db_path()

SOURCE_IDENTIFIER = "operational_db"
DEFAULT_WATERMARK = "2015-12-31 23:00:00"
DEFAULT_BATCH_SIZE = 5000
WATERMARK_FMT = "%Y-%m-%d %H:%M:%S"

# Stable column order for JSON lake batches (matches operational DDL, minus record_id/created_at)
EXPORT_COLUMNS: tuple[str, ...] = (
    "station_name",
    "year",
    "month",
    "day",
    "hour",
    "event_time_local",
    "pm25",
    "pm10",
    "so2",
    "no2",
    "co",
    "o3",
    "temp",
    "pres",
    "dewp",
    "rain",
    "wd",
    "wspd",
)
_EXPORT_COLUMN_SET = frozenset(EXPORT_COLUMNS)


@dataclass(frozen=True)
class DeltaBatch:
    """Rows with event_time_local > watermark, ordered ascending.

    The last hour in the batch is always complete (all stations at that
    event_time), so advancing the next watermark to ``watermark_end`` with
    ``>`` cannot skip sibling stations cut by LIMIT.
    """

    records: list[dict[str, Any]]
    watermark_start: str  # last_watermark passed in (exclusive lower bound)
    watermark_end: str | None  # max event_time_local in batch; None if empty
    record_count: int
    db_path: str
    batch_size_limit: int
    source: str = SOURCE_IDENTIFIER

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_watermark(watermark: str) -> str:
    try:
        datetime.strptime(watermark, WATERMARK_FMT)
    except ValueError as exc:
        raise ValueError(
            f"watermark must be '{WATERMARK_FMT}' (e.g. '{DEFAULT_WATERMARK}'), got {watermark!r}"
        ) from exc
    return watermark


def resolve_db_path(db_path: Path | str | None = None) -> Path:
    path = Path(db_path) if db_path is not None else default_db_path()
    if not path.is_file():
        raise FileNotFoundError(
            f"operational DB not found: {path}; run: py scripts/setup_operational_db.py"
        )
    return path


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = resolve_db_path(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _validate_columns(columns: Sequence[str]) -> tuple[str, ...]:
    cols = tuple(columns)
    unknown = [c for c in cols if c not in _EXPORT_COLUMN_SET]
    if unknown:
        raise ValueError(f"unknown export columns: {unknown}; allowed={list(EXPORT_COLUMNS)}")
    if not cols:
        raise ValueError("columns must be non-empty")
    return cols


def _rows_to_records(rows: list[sqlite3.Row], columns: Sequence[str]) -> list[dict[str, Any]]:
    return [{col: row[col] for col in columns} for row in rows]


def _fetch_at_event_time(
    conn: sqlite3.Connection,
    event_time: str,
    columns: Sequence[str],
) -> list[dict[str, Any]]:
    col_sql = ", ".join(columns)
    sql = f"""
        SELECT {col_sql}
        FROM operational_air_quality
        WHERE event_time_local = ?
        ORDER BY station_name ASC
    """
    rows = conn.execute(sql, (event_time,)).fetchall()
    return _rows_to_records(rows, columns)


def fetch_delta(
    watermark: str = DEFAULT_WATERMARK,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    db_path: Path | str | None = None,
    columns: Sequence[str] = EXPORT_COLUMNS,
) -> DeltaBatch:
    """
    Incremental extract::

        SELECT ... FROM operational_air_quality
        WHERE event_time_local > :watermark
        ORDER BY event_time_local ASC, station_name ASC
        LIMIT :batch_size

    Then complete the trailing hour so LIMIT cannot drop stations that share
    ``watermark_end`` (safe to advance next CDC wm with ``> watermark_end``).
    """
    if batch_size < 1:
        raise ValueError(f"batch_size must be >= 1, got {batch_size}")

    watermark = validate_watermark(watermark)
    cols = _validate_columns(columns)
    path = resolve_db_path(db_path)
    col_sql = ", ".join(cols)

    sql_limited = f"""
        SELECT {col_sql}
        FROM operational_air_quality
        WHERE event_time_local > ?
        ORDER BY event_time_local ASC, station_name ASC
        LIMIT ?
    """

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        limited = _rows_to_records(conn.execute(sql_limited, (watermark, batch_size)).fetchall(), cols)
        if not limited:
            return DeltaBatch(
                records=[],
                watermark_start=watermark,
                watermark_end=None,
                record_count=0,
                db_path=str(path),
                batch_size_limit=batch_size,
            )

        watermark_end = str(limited[-1]["event_time_local"])
        # Keep fully covered hours only, then attach every station at watermark_end.
        complete_prefix = [r for r in limited if r["event_time_local"] < watermark_end]
        trailing_hour = _fetch_at_event_time(conn, watermark_end, cols)
        if not trailing_hour:
            raise RuntimeError(
                f"expected rows at event_time_local={watermark_end!r} after LIMIT fetch"
            )

        records = complete_prefix + trailing_hour
        return DeltaBatch(
            records=records,
            watermark_start=watermark,
            watermark_end=watermark_end,
            record_count=len(records),
            db_path=str(path),
            batch_size_limit=batch_size,
        )
    finally:
        conn.close()


def peek_max_event_time(db_path: Path | str | None = None) -> str | None:
    """Return MAX(event_time_local) in the operational table, or None if empty."""
    path = resolve_db_path(db_path)
    conn = sqlite3.connect(path)
    try:
        row = conn.execute(
            "SELECT MAX(event_time_local) FROM operational_air_quality"
        ).fetchone()
    finally:
        conn.close()
    if row is None or row[0] is None:
        return None
    return str(row[0])
