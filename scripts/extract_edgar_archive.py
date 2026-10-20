#!/usr/bin/env python3
"""Archive-extract EDGAR HTAP v3 PM2.5 for one or more years.

For each year, writes under artifacts/edgar_poc/:
  - edgar_station_monthly_all_sectors_{year}.csv
  - edgar_beijing_bbox_{year}.nc
  - updates edgar_archive_manifest.json

Example:
  py -3 scripts/extract_edgar_archive.py --years 2013 2014
  py -3 scripts/extract_edgar_archive.py --years 2016 2017 \\
      --edgar-glob "data/edgar_HTAPv3_{year}_PM2.5/edgar_HTAPv3_{year}_PM2.5.nc"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import xarray as xr

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("extract_edgar_archive")

DEFAULT_STATIONS_FILE = Path("data/raw/reference/stations.csv")
DEFAULT_OUTPUT_DIR = Path("artifacts/edgar_poc")
DEFAULT_EDGAR_GLOB = "data/edgar_HTAPv3_{year}_PM2.5/edgar_HTAPv3_{year}_PM2.5.nc"

ALL_SECTORS: dict[str, str] = {
    "shipping_intl": "HTAPv3_1_International_Shipping",
    "aviation_domestic": "HTAPv3_2_1_Domestic_Aviation",
    "aviation_intl": "HTAPv3_2_2_International_Aviation",
    "energy": "HTAPv3_3_Energy",
    "industry": "HTAPv3_4_1_Industry",
    "fugitive": "HTAPv3_4_2_Fugitive",
    "solvents": "HTAPv3_4_3_Solvents",
    "road": "HTAPv3_5_1_Road_Transport",
    "brake_tyre": "HTAPv3_5_2_Brake_and_Tyre_wear",
    "shipping_domestic": "HTAPv3_5_3_Domestic_shipping",
    "other_ground_transport": "HTAPv3_5_4_Other_ground_transport",
    "residential": "HTAPv3_6_Residential",
    "waste": "HTAPv3_7_Waste",
    "agri_waste_burning": "HTAPv3_8_1_Agricultural_waste_burning",
    "agri_livestock": "HTAPv3_8_2_Agriculture_livestock",
    "agri_crops": "HTAPv3_8_3_Agriculture_crops",
}

BBOX = {"north": 40.6, "south": 39.5, "west": 115.8, "east": 117.0}


def _sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _load_stations(stations_path: Path) -> pd.DataFrame:
    stations = pd.read_csv(stations_path)
    if "station_name" not in stations.columns and "name" in stations.columns:
        stations = stations.rename(columns={"name": "station_name"})
    if "latitude" not in stations.columns:
        for lat_c, lon_c in (("lat", "lon"), ("Latitude", "Longitude")):
            if lat_c in stations.columns and lon_c in stations.columns:
                stations = stations.rename(columns={lat_c: "latitude", lon_c: "longitude"})
                break
    required = {"station_name", "latitude", "longitude"}
    missing = required - set(stations.columns)
    if missing:
        raise ValueError(f"stations file missing columns: {sorted(missing)}")
    return stations


def extract_year(
    edgar_path: Path,
    stations: pd.DataFrame,
    output_dir: Path,
    year: int,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Opening %s", edgar_path)
    ds = xr.open_dataset(edgar_path)
    try:
        missing = [v for v in ALL_SECTORS.values() if v not in ds.data_vars]
        if missing:
            raise KeyError(f"Missing variables in NetCDF: {missing}")

        years_in_file = sorted({int(pd.to_datetime(t).year) for t in ds.time.values})
        if years_in_file != [year]:
            logger.warning(
                "Requested year=%d but NetCDF time years=%s", year, years_in_file
            )

        var_names = list(ALL_SECTORS.values())
        sub_ds = (
            ds[var_names]
            .sel(
                lat=slice(BBOX["south"], BBOX["north"]),
                lon=slice(BBOX["west"], BBOX["east"]),
            )
            .load()
        )
        logger.info(
            "Beijing bbox %d loaded: time=%d lat=%d lon=%d vars=%d",
            year,
            len(sub_ds.time),
            len(sub_ds.lat),
            len(sub_ds.lon),
            len(var_names),
        )

        rename_map = {v: k for k, v in ALL_SECTORS.items()}
        sub_named = sub_ds.rename(rename_map)
        sub_named["traffic"] = sub_named["road"] + sub_named["brake_tyre"]
        sub_named.attrs.update(
            {
                "title": f"EDGAR HTAP v3 PM2.5 monthly emissions – Beijing bbox {year}",
                "source_file": str(edgar_path),
                "units": "ton/month",
                "bbox": json.dumps(BBOX),
                "year": str(year),
                "created_utc": datetime.now(timezone.utc).isoformat(),
            }
        )
        for v in sub_named.data_vars:
            sub_named[v].attrs.setdefault("units", "ton/month")

        bbox_nc = output_dir / f"edgar_beijing_bbox_{year}.nc"
        encoding = {v: {"zlib": True, "complevel": 4} for v in sub_named.data_vars}
        sub_named.to_netcdf(bbox_nc, encoding=encoding)
        logger.info("Wrote %s (%.1f KB)", bbox_nc, bbox_nc.stat().st_size / 1024)

        records: list[dict[str, Any]] = []
        for _, st in stations.iterrows():
            st_name = str(st["station_name"])
            st_lat = float(st["latitude"])
            st_lon = float(st["longitude"])
            st_pt = sub_named.sel(lat=st_lat, lon=st_lon, method="nearest")
            grid_lat = float(st_pt.lat.values)
            grid_lon = float(st_pt.lon.values)

            for t_idx, t_val in enumerate(st_pt.time.values):
                dt = pd.to_datetime(t_val)
                rec: dict[str, Any] = {
                    "station": st_name,
                    "year": int(dt.year),
                    "month": int(dt.month),
                    "grid_lat": round(grid_lat, 4),
                    "grid_lon": round(grid_lon, 4),
                }
                for feat in ALL_SECTORS:
                    rec[feat] = float(st_pt[feat].values[t_idx])
                rec["traffic"] = rec["road"] + rec["brake_tyre"]
                records.append(rec)

        df = pd.DataFrame(records).sort_values(["station", "year", "month"]).reset_index(drop=True)
        station_csv = output_dir / f"edgar_station_monthly_all_sectors_{year}.csv"
        df.to_csv(station_csv, index=False)
        logger.info("Wrote %s (%d rows)", station_csv, len(df))

        return {
            "year": year,
            "source_nc": str(edgar_path),
            "source_size_bytes": edgar_path.stat().st_size,
            "time_years_in_file": years_in_file,
            "n_stations": int(df["station"].nunique()),
            "n_months": int(df["month"].nunique()),
            "n_station_rows": len(df),
            "outputs": {
                "station_csv": {
                    "path": str(station_csv),
                    "bytes": station_csv.stat().st_size,
                    "sha256": _sha256(station_csv),
                },
                "beijing_bbox_nc": {
                    "path": str(bbox_nc),
                    "bytes": bbox_nc.stat().st_size,
                    "sha256": _sha256(bbox_nc),
                    "shape": {
                        "time": int(len(sub_named.time)),
                        "lat": int(len(sub_named.lat)),
                        "lon": int(len(sub_named.lon)),
                        "vars": list(sub_named.data_vars),
                    },
                },
            },
        }
    finally:
        ds.close()


def update_manifest(output_dir: Path, year_entry: dict[str, Any]) -> Path:
    manifest_path = output_dir / "edgar_archive_manifest.json"
    manifest: dict[str, Any] = {
        "bbox": BBOX,
        "sectors": ALL_SECTORS,
        "derived": {"traffic": "road + brake_tyre"},
        "years": {},
    }
    if manifest_path.exists():
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(existing.get("years"), dict):
                manifest["years"] = existing["years"]
        except json.JSONDecodeError:
            logger.warning("Corrupt manifest at %s – rebuilding years map", manifest_path)

    manifest.setdefault("bbox", BBOX)
    manifest.setdefault("sectors", ALL_SECTORS)
    manifest.setdefault("derived", {"traffic": "road + brake_tyre"})
    manifest.setdefault("years", {})
    year_key = str(year_entry["year"])
    manifest["years"][year_key] = year_entry
    manifest["updated_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["note"] = (
        "Per-year station CSV + Beijing bbox NC. Global source NetCDF can be deleted after verify."
    )
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    logger.info("Updated %s", manifest_path)
    return manifest_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--years",
        type=int,
        nargs="+",
        required=True,
        help="Years to extract, e.g. 2013 2014",
    )
    parser.add_argument(
        "--edgar-glob",
        type=str,
        default=DEFAULT_EDGAR_GLOB,
        help='Path template with {year}, default: %(default)s',
    )
    parser.add_argument("--stations-file", type=Path, default=DEFAULT_STATIONS_FILE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    if not args.stations_file.exists():
        raise SystemExit(f"Stations file not found: {args.stations_file}")
    stations = _load_stations(args.stations_file)

    for year in args.years:
        edgar_path = Path(args.edgar_glob.format(year=year))
        if not edgar_path.exists():
            raise SystemExit(f"EDGAR file not found for {year}: {edgar_path}")
        entry = extract_year(edgar_path, stations, args.output_dir, year)
        update_manifest(args.output_dir, entry)
        logger.info(
            "DONE %d: %.1f KB CSV + %.1f KB bbox NC",
            year,
            entry["outputs"]["station_csv"]["bytes"] / 1024,
            entry["outputs"]["beijing_bbox_nc"]["bytes"] / 1024,
        )


if __name__ == "__main__":
    main()
