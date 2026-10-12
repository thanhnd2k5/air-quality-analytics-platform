#!/usr/bin/env python3
"""Download the UCI Beijing Multi-Site Air Quality dataset into data/raw/uci/.

Source : https://archive.ics.uci.edu/dataset/501/beijing+multi+site+air+quality
DOI    : 10.24432/C5RK5G — Chen, S. (2017)
License: Creative Commons Attribution 4.0 International (CC BY 4.0)

The UCI zip nests a second zip (PRSA2017_Data_20130301-20170228.zip) that holds
the 12 station CSVs. Each extracted file is checked against the byte size in
data/raw/reference/file_inventory.csv. Files that already match are skipped.

Examples:
    python scripts/download_uci_dataset.py
    python scripts/download_uci_dataset.py --force
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UCI_URL = (
    "https://archive.ics.uci.edu/static/public/501/"
    "beijing+multi+site+air+quality+data.zip"
)
INNER_ZIP = "PRSA2017_Data_20130301-20170228.zip"
INVENTORY = ROOT / "data" / "raw" / "reference" / "file_inventory.csv"
OUT_DIR = ROOT / "data" / "raw" / "uci"


def expected_sizes(inventory: Path = INVENTORY) -> dict[str, int]:
    with inventory.open(encoding="utf-8") as fh:
        return {row["file_name"]: int(row["file_size_bytes"]) for row in csv.DictReader(fh)}


def local_files_ok(sizes: dict[str, int], out_dir: Path = OUT_DIR) -> bool:
    return all(
        (out_dir / name).is_file() and (out_dir / name).stat().st_size == size
        for name, size in sizes.items()
    )


def download(url: str = UCI_URL, timeout: int = 120) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 — fixed https URL
        return resp.read()


def extract_station_csvs(outer_zip: bytes, sizes: dict[str, int], out_dir: Path = OUT_DIR) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(outer_zip)) as outer:
        inner_bytes = outer.read(INNER_ZIP)
    results = []
    with zipfile.ZipFile(io.BytesIO(inner_bytes)) as inner:
        members = {Path(m).name: m for m in inner.namelist() if m.endswith(".csv")}
        for name, size in sorted(sizes.items()):
            if name not in members:
                raise FileNotFoundError(f"{name} not found inside {INNER_ZIP}")
            data = inner.read(members[name])
            if len(data) != size:
                raise ValueError(f"{name}: size {len(data)} != inventory {size}")
            (out_dir / name).write_bytes(data)
            results.append({"file": name, "bytes": len(data), "status": "written"})
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Download UCI PRSA dataset (12 station CSVs)")
    parser.add_argument("--force", action="store_true", help="Re-download even if files match")
    args = parser.parse_args()

    sizes = expected_sizes()
    if not args.force and local_files_ok(sizes):
        print(json.dumps({"status": "skipped", "reason": "all 12 CSVs present with expected size"}))
        return 0

    print(f"Downloading {UCI_URL} ...", file=sys.stderr)
    results = extract_station_csvs(download(), sizes)
    print(json.dumps({"status": "ok", "files": len(results), "out_dir": str(OUT_DIR)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
