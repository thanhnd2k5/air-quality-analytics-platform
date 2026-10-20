#!/usr/bin/env python3
"""Split UCI PRSA into Historical File (<=2015) + Simulated Operational DB (2016->2017).

Phase 1 of docs/OPERATIONAL_DB_INGESTION_DESIGN.md:

  - Archive CSV at data/raw/uci/ keeps rows with event_time_local <= 2015-12-31 23:00
  - SQLite data/raw/database/prsa_operational.db loads 2016-01-01 -> 2017-02-28
  - Assert |File| + |DB| == 420_768 (no fabricated measurements)

Examples:
    py scripts/setup_operational_db.py
    py scripts/setup_operational_db.py --dry-run
    py scripts/setup_operational_db.py --force
    py scripts/setup_operational_db.py --skip-truncate-csv
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
UCI_DIR = ROOT / "data" / "raw" / "uci"
DB_DIR = ROOT / "data" / "raw" / "database"
DB_PATH = DB_DIR / "prsa_operational.db"
INVENTORY = ROOT / "data" / "raw" / "reference" / "file_inventory.csv"

FILE_END = pd.Timestamp("2015-12-31 23:00:00")
DB_START = pd.Timestamp("2016-01-01 00:00:00")
DB_END = pd.Timestamp("2017-02-28 23:00:00")
EXPECTED_DB_MIN = "2016-01-01 00:00:00"
EXPECTED_DB_MAX = "2017-02-28 23:00:00"
EXPECTED_STATIONS = 12

# Inclusive hourly ranges x 12 stations (design v2.1 had off-by-1-day figures)
EXPECTED_FILE_ROWS = 298_368  # 24_864 h x 12; 2013-03-01 -> 2015-12-31
EXPECTED_DB_ROWS = 122_400  # 10_200 h x 12; 2016-01-01 -> 2017-02-28
EXPECTED_TOTAL_ROWS = 420_768

UCI_SOURCE_COLUMNS = (
    "No",
    "year",
    "month",
    "day",
    "hour",
    "PM2.5",
    "PM10",
    "SO2",
    "NO2",
    "CO",
    "O3",
    "TEMP",
    "PRES",
    "DEWP",
    "RAIN",
    "wd",
    "WSPM",
    "station",
)

DDL = """
CREATE TABLE operational_air_quality (
    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_name TEXT NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    day INTEGER NOT NULL,
    hour INTEGER NOT NULL,
    event_time_local TEXT NOT NULL,
    pm25 REAL,
    pm10 REAL,
    so2 REAL,
    no2 REAL,
    co REAL,
    o3 REAL,
    temp REAL,
    pres REAL,
    dewp REAL,
    rain REAL,
    wd TEXT,
    wspd REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (station_name, event_time_local)
);

CREATE INDEX idx_station_event_time
ON operational_air_quality(station_name, event_time_local);

CREATE INDEX idx_event_time
ON operational_air_quality(event_time_local);
"""

# Design DDL names <- UCI CSV columns
UCI_TO_DB: dict[str, str] = {
    "station": "station_name",
    "year": "year",
    "month": "month",
    "day": "day",
    "hour": "hour",
    "PM2.5": "pm25",
    "PM10": "pm10",
    "SO2": "so2",
    "NO2": "no2",
    "CO": "co",
    "O3": "o3",
    "TEMP": "temp",
    "PRES": "pres",
    "DEWP": "dewp",
    "RAIN": "rain",
    "wd": "wd",
    "WSPM": "wspd",
}

DB_INSERT_COLUMNS = (
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


def emit(payload: dict, *, stream=sys.stdout) -> None:
    """JSON to console; ensure_ascii avoids Windows cp1252 UnicodeEncodeError."""
    print(json.dumps(payload, ensure_ascii=True, indent=2), file=stream)


def inventory_files(inventory: Path = INVENTORY) -> list[dict[str, str]]:
    df = pd.read_csv(inventory)
    rows = df[["station_name", "file_name"]].astype(str)
    return rows.to_dict(orient="records")


def load_station_csv(path: Path, expected_station: str) -> pd.DataFrame:
    df = pd.read_csv(path, na_values=["NA", "NaN", ""], keep_default_na=True)
    required = tuple(UCI_TO_DB.keys())
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{path.name}: missing columns {missing}")

    time_parts = ["year", "month", "day", "hour"]
    if df[time_parts].isna().any().any():
        raise ValueError(f"{path.name}: null year/month/day/hour values")

    df["event_time_local"] = pd.to_datetime(
        {
            "year": df["year"].astype(int),
            "month": df["month"].astype(int),
            "day": df["day"].astype(int),
            "hour": df["hour"].astype(int),
        }
    )

    stations = set(df["station"].astype(str).str.strip().unique())
    if stations != {expected_station}:
        raise ValueError(
            f"{path.name}: station column {sorted(stations)} != expected '{expected_station}'"
        )
    return df


def split_frames(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    file_mask = df["event_time_local"] <= FILE_END
    db_mask = (df["event_time_local"] >= DB_START) & (df["event_time_local"] <= DB_END)
    file_df = df.loc[file_mask].copy()
    db_df = df.loc[db_mask].copy()

    gap = ~(file_mask | db_mask)
    if gap.any():
        raise RuntimeError(
            f"Rows outside File+DB windows: {int(gap.sum())} "
            f"(min={df.loc[gap, 'event_time_local'].min()}, "
            f"max={df.loc[gap, 'event_time_local'].max()})"
        )

    if len(file_df) + len(db_df) != len(df):
        raise RuntimeError(
            f"Split row count mismatch: file={len(file_df)} db={len(db_df)} src={len(df)}"
        )
    return file_df, db_df


def to_db_records(db_df: pd.DataFrame) -> pd.DataFrame:
    out = db_df.rename(columns=UCI_TO_DB).copy()
    out["event_time_local"] = out["event_time_local"].dt.strftime("%Y-%m-%d %H:%M:%S")
    return out[list(DB_INSERT_COLUMNS)]


def write_archive_csv(path: Path, file_df: pd.DataFrame) -> int:
    """Write historical rows with original UCI column order (drop helper col)."""
    cols = [c for c in file_df.columns if c != "event_time_local"]
    ordered = [c for c in UCI_SOURCE_COLUMNS if c in cols] + [
        c for c in cols if c not in UCI_SOURCE_COLUMNS
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    file_df[ordered].to_csv(path, index=False)
    return len(file_df)


def write_archive_csvs_atomic(items: list[tuple[Path, pd.DataFrame]]) -> list[dict]:
    """Write all archives to *.csv.tmp first, then os.replace into place.

    If writing temps fails, originals stay untouched. Replace is per-file atomic
    on the same volume; temps are cleaned on failure.
    """
    staged: list[tuple[Path, Path, int]] = []
    try:
        for path, file_df in items:
            tmp = path.with_name(path.name + ".tmp")
            n = write_archive_csv(tmp, file_df)
            staged.append((tmp, path, n))

        results = []
        for tmp, path, n in staged:
            tmp.replace(path)
            results.append({"file": path.name, "rows": n})
        return results
    except Exception:
        for tmp, _path, _n in staged:
            if tmp.exists():
                tmp.unlink()
        raise


def create_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    conn.executescript(DDL)
    return conn


def insert_db_rows(conn: sqlite3.Connection, records: pd.DataFrame) -> int:
    if records.empty:
        return 0
    placeholders = ", ".join("?" for _ in DB_INSERT_COLUMNS)
    cols = ", ".join(DB_INSERT_COLUMNS)
    sql = f"INSERT INTO operational_air_quality ({cols}) VALUES ({placeholders})"
    rows = [
        tuple(None if pd.isna(v) else v for v in row)
        for row in records.itertuples(index=False, name=None)
    ]
    conn.executemany(sql, rows)
    return len(rows)


def reconcile(file_rows: int, db_rows: int) -> dict:
    ok = (
        file_rows == EXPECTED_FILE_ROWS
        and db_rows == EXPECTED_DB_ROWS
        and file_rows + db_rows == EXPECTED_TOTAL_ROWS
    )
    return {
        "file_rows": file_rows,
        "db_rows": db_rows,
        "total_rows": file_rows + db_rows,
        "expected_file_rows": EXPECTED_FILE_ROWS,
        "expected_db_rows": EXPECTED_DB_ROWS,
        "expected_total_rows": EXPECTED_TOTAL_ROWS,
        "ok": ok,
    }


def _health_row(conn: sqlite3.Connection) -> tuple | None:
    try:
        return conn.execute(
            """
            SELECT
                COUNT(*) AS n,
                COUNT(DISTINCT station_name) AS stations,
                MIN(event_time_local) AS tmin,
                MAX(event_time_local) AS tmax
            FROM operational_air_quality
            """
        ).fetchone()
    except sqlite3.Error:
        return None


def row_looks_healthy(row: tuple | None) -> bool:
    if row is None:
        return False
    n, stations, tmin, tmax = row
    return (
        int(n) == EXPECTED_DB_ROWS
        and int(stations) == EXPECTED_STATIONS
        and tmin == EXPECTED_DB_MIN
        and tmax == EXPECTED_DB_MAX
    )


def db_is_healthy(db_path: Path) -> bool:
    """True when DB has expected row count, time span, and 12 stations."""
    if not db_path.is_file():
        return False
    conn = sqlite3.connect(db_path)
    try:
        return row_looks_healthy(_health_row(conn))
    finally:
        conn.close()


def archive_already_truncated(uci_dir: Path, stations: list[dict[str, str]]) -> bool:
    """True when local CSVs are already the historical File channel (no 2016+ rows)."""
    total = 0
    for row in stations:
        path = uci_dir / row["file_name"]
        if not path.is_file():
            return False
        df = pd.read_csv(path, usecols=["year", "month", "day", "hour", "station"])
        total += len(df)
        names = set(df["station"].astype(str).str.strip().unique())
        if names != {row["station_name"]}:
            return False
        tmax = pd.to_datetime(
            {
                "year": df["year"].astype(int),
                "month": df["month"].astype(int),
                "day": df["day"].astype(int),
                "hour": df["hour"].astype(int),
            }
        ).max()
        if tmax != FILE_END:
            return False
    return total == EXPECTED_FILE_ROWS


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build historical UCI File archive + simulated operational SQLite DB"
    )
    parser.add_argument("--uci-dir", type=Path, default=UCI_DIR, help="Directory of UCI station CSVs")
    parser.add_argument("--db-path", type=Path, default=DB_PATH, help="Output SQLite path")
    parser.add_argument(
        "--skip-truncate-csv",
        action="store_true",
        help="Only build DB; leave full UCI CSVs unchanged",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild even if DB/archive already look healthy",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute splits and reconcile without writing DB/CSV",
    )
    args = parser.parse_args()

    stations = inventory_files()
    if len(stations) != EXPECTED_STATIONS:
        emit(
            {
                "status": "failed",
                "message": f"expected {EXPECTED_STATIONS} stations, got {len(stations)}",
            },
            stream=sys.stderr,
        )
        return 1

    if (
        not args.dry_run
        and not args.force
        and db_is_healthy(args.db_path)
        and (args.skip_truncate_csv or archive_already_truncated(args.uci_dir, stations))
    ):
        emit(
            {
                "status": "skipped",
                "reason": "operational DB and File archive already healthy "
                "(use --force to rebuild)",
                "reconcile": reconcile(EXPECTED_FILE_ROWS, EXPECTED_DB_ROWS),
                "db_path": str(args.db_path),
            }
        )
        return 0

    file_total = 0
    db_total = 0
    per_station: list[dict] = []
    pending_db: list[pd.DataFrame] = []
    pending_csv: list[tuple[Path, pd.DataFrame]] = []

    for row in stations:
        station = row["station_name"]
        path = args.uci_dir / row["file_name"]
        if not path.is_file():
            emit(
                {
                    "status": "failed",
                    "message": f"missing {path}; run: py scripts/download_uci_dataset.py",
                },
                stream=sys.stderr,
            )
            return 1

        try:
            src = load_station_csv(path, station)
        except ValueError as exc:
            emit({"status": "failed", "message": str(exc)}, stream=sys.stderr)
            return 1

        tmax = src["event_time_local"].max()
        if tmax < DB_END:
            emit(
                {
                    "status": "failed",
                    "message": (
                        f"{path.name} ends at {tmax} - need full UCI through 2017-02-28. "
                        "Restore with: py scripts/download_uci_dataset.py --force"
                    ),
                },
                stream=sys.stderr,
            )
            return 1

        file_df, db_df = split_frames(src)
        file_total += len(file_df)
        db_total += len(db_df)
        per_station.append(
            {
                "station": station,
                "source_rows": len(src),
                "file_rows": len(file_df),
                "db_rows": len(db_df),
                "file_min": str(file_df["event_time_local"].min()),
                "file_max": str(file_df["event_time_local"].max()),
                "db_min": str(db_df["event_time_local"].min()) if len(db_df) else None,
                "db_max": str(db_df["event_time_local"].max()) if len(db_df) else None,
            }
        )
        pending_db.append(to_db_records(db_df))
        if not args.skip_truncate_csv:
            pending_csv.append((path, file_df))

    check = reconcile(file_total, db_total)
    if not check["ok"]:
        emit(
            {"status": "failed", "reconcile": check, "per_station": per_station},
            stream=sys.stderr,
        )
        return 1

    if args.dry_run:
        emit(
            {
                "status": "dry_run_ok",
                "reconcile": check,
                "per_station": per_station,
                "db_path": str(args.db_path),
                "truncate_csv": not args.skip_truncate_csv,
            }
        )
        return 0

    conn = create_db(args.db_path)
    try:
        inserted = 0
        for chunk in pending_db:
            inserted += insert_db_rows(conn, chunk)
        conn.commit()
        health = _health_row(conn)
        if not row_looks_healthy(health):
            raise RuntimeError(f"DB health check failed after insert: {health}")
    except Exception:
        conn.close()
        if args.db_path.exists():
            args.db_path.unlink()
        raise
    else:
        conn.close()

    truncated: list[dict] = []
    if pending_csv:
        truncated = write_archive_csvs_atomic(pending_csv)

    emit(
        {
            "status": "ok",
            "reconcile": check,
            "db_path": str(args.db_path),
            "db_inserted": inserted,
            "csv_truncated": truncated,
            "note": (
                "UCI CSVs truncated to <=2015-12-31; restore full package with "
                "py scripts/download_uci_dataset.py --force then re-run this script."
                if truncated
                else "Full UCI CSVs left unchanged (--skip-truncate-csv)."
            ),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
