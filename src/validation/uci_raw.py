"""Light validation for UCI raw CSVs before MinIO ingestion (Phase 3)."""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from pathlib import Path

# Canonical 18 columns from Phase 1 profiling / DATA_GUIDE
UCI_REQUIRED_COLUMNS: tuple[str, ...] = (
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


@dataclass(frozen=True)
class InventoryRow:
    station_name: str
    file_name: str
    relative_path: str
    inventory_status: str


@dataclass(frozen=True)
class UciRawValidationResult:
    station: str
    source_path: Path
    file_name: str
    relative_path: str
    columns: tuple[str, ...]
    ok: bool
    message: str


def default_inventory_path() -> Path:
    env = os.getenv("UCI_INVENTORY_PATH")
    if env:
        return Path(env)
    return Path("data/raw/reference/file_inventory.csv")


def default_uci_raw_dir() -> Path:
    env = os.getenv("UCI_RAW_DIR")
    if env:
        return Path(env)
    return Path("data/raw/uci")


def load_inventory(inventory_path: Path | None = None) -> dict[str, InventoryRow]:
    path = inventory_path or default_inventory_path()
    if not path.is_file():
        raise FileNotFoundError(f"Inventory not found: {path}")

    by_station: dict[str, InventoryRow] = {}
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            station = (row.get("station_name") or "").strip()
            if not station:
                continue
            by_station[station] = InventoryRow(
                station_name=station,
                file_name=(row.get("file_name") or "").strip(),
                relative_path=(row.get("relative_path") or "").strip(),
                inventory_status=(row.get("inventory_status") or "").strip(),
            )
    if not by_station:
        raise ValueError(f"No stations found in inventory: {path}")
    return by_station


def resolve_station_csv(
    station: str,
    *,
    inventory_path: Path | None = None,
    uci_raw_dir: Path | None = None,
) -> tuple[InventoryRow, Path]:
    inventory = load_inventory(inventory_path)
    if station not in inventory:
        known = ", ".join(sorted(inventory))
        raise KeyError(f"Station '{station}' not in inventory. Known: {known}")

    row = inventory[station]
    raw_dir = uci_raw_dir or default_uci_raw_dir()
    # Prefer file under mounted/raw dir; fall back to relative_path from repo root
    candidate = raw_dir / row.file_name
    if not candidate.is_file():
        alt = Path(row.relative_path)
        if alt.is_file():
            candidate = alt
        else:
            raise FileNotFoundError(
                f"UCI CSV for {station} not found at {candidate} or {alt}"
            )
    return row, candidate


def read_csv_header(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
    if not header:
        raise ValueError(f"Empty CSV (no header): {path}")
    return [c.strip().strip('"') for c in header]


def validate_uci_raw_file(
    station: str,
    *,
    inventory_path: Path | None = None,
    uci_raw_dir: Path | None = None,
) -> UciRawValidationResult:
    """
    Light checks only (Phase 3):
    - station is in inventory
    - file exists
    - header has exactly the 18 canonical columns
    - station column values match the expected station (sample first data row)
    """
    row, path = resolve_station_csv(
        station, inventory_path=inventory_path, uci_raw_dir=uci_raw_dir
    )
    columns = tuple(read_csv_header(path))

    if columns != UCI_REQUIRED_COLUMNS:
        return UciRawValidationResult(
            station=station,
            source_path=path,
            file_name=row.file_name,
            relative_path=row.relative_path,
            columns=columns,
            ok=False,
            message=(
                f"Schema mismatch for {station}: expected {len(UCI_REQUIRED_COLUMNS)} "
                f"canonical columns, got {list(columns)}"
            ),
        )

    # Spot-check station column on first data row (no full scan / no transform)
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        first = next(reader, None)
    if first is None:
        return UciRawValidationResult(
            station=station,
            source_path=path,
            file_name=row.file_name,
            relative_path=row.relative_path,
            columns=columns,
            ok=False,
            message=f"CSV has header but no data rows: {path}",
        )

    actual_station = (first.get("station") or "").strip().strip('"')
    if actual_station != station:
        return UciRawValidationResult(
            station=station,
            source_path=path,
            file_name=row.file_name,
            relative_path=row.relative_path,
            columns=columns,
            ok=False,
            message=(
                f"Station column mismatch: expected '{station}', "
                f"got '{actual_station}' in first row of {path.name}"
            ),
        )

    return UciRawValidationResult(
        station=station,
        source_path=path,
        file_name=row.file_name,
        relative_path=row.relative_path,
        columns=columns,
        ok=True,
        message="ok",
    )
