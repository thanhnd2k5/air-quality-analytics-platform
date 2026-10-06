"""Unit tests for Phase 3 UCI raw validation + object key builder."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from src.ingestion.uci_to_minio import build_meta_key, build_object_key
from src.validation.uci_raw import UCI_REQUIRED_COLUMNS, validate_uci_raw_file


def _write_uci_csv(path: Path, station: str, columns: list[str] | None = None) -> None:
    cols = columns or list(UCI_REQUIRED_COLUMNS)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols)
        writer.writeheader()
        row = {c: "0" for c in cols}
        if "station" in cols:
            row["station"] = station
        if "No" in cols:
            row["No"] = "1"
        if "year" in cols:
            row["year"] = "2013"
        if "month" in cols:
            row["month"] = "3"
        if "day" in cols:
            row["day"] = "1"
        if "hour" in cols:
            row["hour"] = "0"
        writer.writerow(row)


def _write_inventory(path: Path, station: str, file_name: str) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "station_id",
                "station_name",
                "file_name",
                "relative_path",
                "inventory_status",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "station_id": "1",
                "station_name": station,
                "file_name": file_name,
                "relative_path": f"data/raw/uci/{file_name}",
                "inventory_status": "VERIFIED",
            }
        )


def test_build_object_key_uses_station_and_date():
    key = build_object_key(
        "Wanshouxigong",
        "PRSA_Data_Wanshouxigong_20130301-20170228.csv",
        ingestion_date="2026-10-06",
    )
    assert (
        key
        == "raw/uci/air_quality/station=Wanshouxigong/ingestion_date=2026-10-06/"
        "PRSA_Data_Wanshouxigong_20130301-20170228.csv"
    )
    assert build_meta_key(key) == f"{key}.meta.json"


def test_validate_uci_raw_ok(tmp_path: Path):
    station = "Wanshouxigong"
    file_name = "PRSA_Data_Wanshouxigong_20130301-20170228.csv"
    uci_dir = tmp_path / "uci"
    uci_dir.mkdir()
    csv_path = uci_dir / file_name
    _write_uci_csv(csv_path, station)

    inventory = tmp_path / "file_inventory.csv"
    _write_inventory(inventory, station, file_name)

    result = validate_uci_raw_file(
        station, inventory_path=inventory, uci_raw_dir=uci_dir
    )
    assert result.ok
    assert result.source_path == csv_path
    assert result.columns == UCI_REQUIRED_COLUMNS


def test_validate_uci_raw_schema_mismatch(tmp_path: Path):
    station = "Wanshouxigong"
    file_name = "PRSA_Data_Wanshouxigong_20130301-20170228.csv"
    uci_dir = tmp_path / "uci"
    uci_dir.mkdir()
    _write_uci_csv(uci_dir / file_name, station, columns=["No", "station"])

    inventory = tmp_path / "file_inventory.csv"
    _write_inventory(inventory, station, file_name)

    result = validate_uci_raw_file(
        station, inventory_path=inventory, uci_raw_dir=uci_dir
    )
    assert not result.ok
    assert "Schema mismatch" in result.message


def test_validate_unknown_station(tmp_path: Path):
    inventory = tmp_path / "file_inventory.csv"
    _write_inventory(inventory, "Wanshouxigong", "x.csv")
    with pytest.raises(KeyError, match="not in inventory"):
        validate_uci_raw_file(
            "NoSuchStation",
            inventory_path=inventory,
            uci_raw_dir=tmp_path,
        )
