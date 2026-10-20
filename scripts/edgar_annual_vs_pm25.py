#!/usr/bin/env python3
"""City-level EDGAR annual index vs observed Beijing PM2.5.

Explanatory only. Does not touch HistGB features, the model lock, or the warehouse.

Reads the five extracted station-month CSVs, sums energy / industry / residential
on unique 0.1° cells (shared stations are not double-counted), and compares:

  - calendar years 2014, 2015, 2016 (full observed years)
  - heating seasons Nov–Feb: 2013/14, 2014/15, 2015/16, 2016/17

PM2.5 is the mean of non-null station-hours. UCI archive CSVs cover
2013-03-01 through 2015-12-31. The operational SQLite covers 2016-01-01
through 2017-02-28. Calendar-year 2013 and 2017 emissions are written for
the level change, without a full-year PM2.5 mean.

Example:
    py -3 scripts/edgar_annual_vs_pm25.py
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
POC = ROOT / "artifacts" / "edgar_poc"
FIG_DIR = POC / "figures"
UCI_DIR = ROOT / "data" / "raw" / "uci"
DB_PATH = ROOT / "data" / "raw" / "database" / "prsa_operational.db"

SECTORS = ("energy", "industry", "residential")
EDGAR_FILES = {
    2013: POC / "edgar_station_monthly_all_sectors_2013.csv",
    2014: POC / "edgar_station_monthly_all_sectors_2014.csv",
    2015: POC / "edgar_station_monthly_all_sectors.csv",
    2016: POC / "edgar_station_monthly_all_sectors_2016.csv",
    2017: POC / "edgar_station_monthly_all_sectors_2017.csv",
}

HEATING = (
    ("2013/14", ((2013, 11), (2013, 12), (2014, 1), (2014, 2))),
    ("2014/15", ((2014, 11), (2014, 12), (2015, 1), (2015, 2))),
    ("2015/16", ((2015, 11), (2015, 12), (2016, 1), (2016, 2))),
    ("2016/17", ((2016, 11), (2016, 12), (2017, 1), (2017, 2))),
)
CALENDAR_OVERLAP = (2014, 2015, 2016)


def _load_edgar() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for year, path in EDGAR_FILES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        df = pd.read_csv(path)
        years = sorted(df["year"].unique().tolist())
        if years != [year]:
            raise ValueError(f"{path.name} has years {years}, expected [{year}]")
        frames.append(df)
    raw = pd.concat(frames, ignore_index=True)
    cells = raw.drop_duplicates(["year", "month", "grid_lat", "grid_lon"]).copy()
    n_cells = cells.groupby(["year", "month"]).size()
    if not (n_cells == 9).all():
        raise ValueError(f"expected 9 unique cells per month, got {n_cells.unique().tolist()}")
    return cells


def _load_pm25() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    paths = sorted(UCI_DIR.glob("PRSA_Data_*.csv"))
    if len(paths) != 12:
        raise FileNotFoundError(f"expected 12 UCI CSVs in {UCI_DIR}, found {len(paths)}")
    for path in paths:
        df = pd.read_csv(path, usecols=["year", "month", "PM2.5", "station"])
        frames.append(df.rename(columns={"PM2.5": "pm25", "station": "station_name"}))
    uci = pd.concat(frames, ignore_index=True)
    uci_end = (int(uci["year"].max()), int(uci.loc[uci["year"].idxmax(), "month"]))
    if uci["year"].max() > 2015:
        raise ValueError(f"UCI CSV extends past 2015 ({uci_end}); archive/DB split changed")

    if not DB_PATH.is_file():
        raise FileNotFoundError(DB_PATH)
    with sqlite3.connect(DB_PATH) as con:
        op = pd.read_sql_query(
            """
            SELECT station_name,
                   CAST(strftime('%Y', event_time_local) AS INTEGER) AS year,
                   CAST(strftime('%m', event_time_local) AS INTEGER) AS month,
                   pm25
            FROM operational_air_quality
            """,
            con,
        )
    if op.empty:
        raise ValueError(f"no rows in {DB_PATH}")
    if int(op["year"].min()) < 2016:
        raise ValueError("operational DB contains rows before 2016; overlap with UCI CSV")

    out = pd.concat(
        [
            uci.assign(source="uci_csv"),
            op.assign(source="operational_db"),
        ],
        ignore_index=True,
    )
    return out


def _month_mask(df: pd.DataFrame, months: tuple[tuple[int, int], ...]) -> pd.Series:
    key = list(zip(df["year"].astype(int), df["month"].astype(int)))
    wanted = set(months)
    return pd.Series([pair in wanted for pair in key], index=df.index)


def _sum_sectors(cells: pd.DataFrame, mask: pd.Series) -> dict[str, float]:
    chunk = cells.loc[mask]
    if chunk.empty:
        raise ValueError("EDGAR slice is empty")
    totals = chunk[list(SECTORS)].sum()
    return {f"{name}_ton": float(totals[name]) for name in SECTORS}


def _pm25_stats(obs: pd.DataFrame, mask: pd.Series) -> dict[str, float | int | None]:
    chunk = obs.loc[mask]
    values = chunk["pm25"].dropna()
    if values.empty:
        return {
            "pm25_mean_ug_m3": None,
            "pm25_n": 0,
            "n_stations": 0,
        }
    return {
        "pm25_mean_ug_m3": float(values.mean()),
        "pm25_n": int(values.shape[0]),
        "n_stations": int(chunk.loc[chunk["pm25"].notna(), "station_name"].nunique()),
    }


def _with_index(rows: list[dict], base_label: str) -> list[dict]:
    base = next(row for row in rows if row["label"] == base_label)
    out: list[dict] = []
    for row in rows:
        item = dict(row)
        item["index_base"] = base_label
        for name in (*SECTORS, "pm25"):
            src = f"{name}_ton" if name != "pm25" else "pm25_mean_ug_m3"
            base_val = base[src]
            val = row[src]
            if val is None or base_val in (None, 0):
                item[f"{name}_index"] = None
            else:
                item[f"{name}_index"] = float(val) / float(base_val) * 100.0
        out.append(item)
    return out


def _corr_block(frame: pd.DataFrame) -> dict:
    block: dict[str, dict] = {"n": int(len(frame))}
    for name in SECTORS:
        pair = frame[[f"{name}_ton", "pm25_mean_ug_m3"]].dropna()
        block[name] = {
            "n": int(len(pair)),
            "pearson": None if len(pair) < 2 else float(pair.iloc[:, 0].corr(pair.iloc[:, 1], method="pearson")),
            "spearman": None if len(pair) < 2 else float(pair.iloc[:, 0].corr(pair.iloc[:, 1], method="spearman")),
        }
    return block


def _plot(calendar: pd.DataFrame, heating: pd.DataFrame, path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.4), sharey=True)
    series = (
        ("energy_index", "Energy"),
        ("industry_index", "Industry"),
        ("residential_index", "Residential"),
        ("pm25_index", "PM2.5"),
    )
    colors = {
        "energy_index": "#c47b2b",
        "industry_index": "#3d6b99",
        "residential_index": "#b04a4a",
        "pm25_index": "#1f1f1f",
    }
    panels = (
        (axes[0], calendar, "Calendar year (2014 = 100)"),
        (axes[1], heating, "Heating season Nov–Feb (2013/14 = 100)"),
    )
    for ax, frame, title in panels:
        x = list(range(len(frame)))
        for col, label in series:
            ax.plot(
                x,
                frame[col],
                marker="o",
                color=colors[col],
                linewidth=1.8 if col != "pm25_index" else 2.2,
                label=label,
            )
        ax.set_xticks(x)
        ax.set_xticklabels(frame["label"].tolist())
        ax.set_title(title)
        ax.axhline(100, color="#bbbbbb", linewidth=0.8, zorder=0)
        ax.grid(axis="y", color="#eeeeee")
    axes[0].set_ylabel("Index")
    axes[1].legend(frameon=False, loc="best")
    fig.suptitle("Beijing EDGAR PM2.5 emissions and observed PM2.5", fontsize=12)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    cells = _load_edgar()
    obs = _load_pm25()

    emission_rows: list[dict] = []
    for year in range(2013, 2018):
        mask = cells["year"] == year
        row = {
            "panel": "emission_annual",
            "label": str(year),
            "pm25_coverage": "not_compared",
            "n_grid_cells": 9,
            **_sum_sectors(cells, mask),
            "pm25_mean_ug_m3": None,
            "pm25_n": None,
            "n_stations": None,
        }
        emission_rows.append(row)
    emission_rows = _with_index(emission_rows, "2013")

    calendar_rows: list[dict] = []
    for year in CALENDAR_OVERLAP:
        e_mask = cells["year"] == year
        o_mask = obs["year"] == year
        calendar_rows.append(
            {
                "panel": "calendar_overlap",
                "label": str(year),
                "pm25_coverage": "full_year",
                "n_grid_cells": 9,
                **_sum_sectors(cells, e_mask),
                **_pm25_stats(obs, o_mask),
            }
        )
    calendar_rows = _with_index(calendar_rows, "2014")

    heating_rows: list[dict] = []
    for label, months in HEATING:
        heating_rows.append(
            {
                "panel": "heating_season",
                "label": label,
                "pm25_coverage": "nov_feb",
                "n_grid_cells": 9,
                **_sum_sectors(cells, _month_mask(cells, months)),
                **_pm25_stats(obs, _month_mask(obs, months)),
            }
        )
    heating_rows = _with_index(heating_rows, "2013/14")

    table = pd.DataFrame([*emission_rows, *calendar_rows, *heating_rows])
    col_order = [
        "panel",
        "label",
        "index_base",
        "pm25_coverage",
        "n_grid_cells",
        "energy_ton",
        "industry_ton",
        "residential_ton",
        "energy_index",
        "industry_index",
        "residential_index",
        "pm25_mean_ug_m3",
        "pm25_index",
        "pm25_n",
        "n_stations",
    ]
    table = table[col_order]
    for col in ("pm25_n", "n_stations"):
        table[col] = table[col].astype("Int64")

    POC.mkdir(parents=True, exist_ok=True)
    csv_path = POC / "edgar_city_year_index.csv"
    table.to_csv(csv_path, index=False)

    calendar = table[table["panel"] == "calendar_overlap"].reset_index(drop=True)
    heating = table[table["panel"] == "heating_season"].reset_index(drop=True)
    fig_path = FIG_DIR / "edgar_vs_pm25_annual.png"
    _plot(calendar, heating, fig_path)

    summary = {
        "pm25_sources": {
            "uci_csv": "data/raw/uci/PRSA_Data_*.csv through 2015-12-31",
            "operational_db": "data/raw/database/prsa_operational.db from 2016-01-01",
            "null_pm25": "excluded from the mean",
            "spatial_sum": "9 unique 0.1 degree cells; shared stations not double-counted",
        },
        "correlation": {
            "calendar_overlap": _corr_block(calendar),
            "heating_season": _corr_block(heating),
        },
        "outputs": {
            "csv": str(csv_path.relative_to(ROOT)).replace("\\", "/"),
            "figure": str(fig_path.relative_to(ROOT)).replace("\\", "/"),
        },
        "note": (
            "n is 3 calendar years and 4 heating seasons. "
            "Coefficients illustrate co-movement. They are not a significance test "
            "and not a reason to add EDGAR to the forecast model."
        ),
    }
    summary_path = POC / "edgar_city_year_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(table.to_string(index=False))
    print(json.dumps(summary["correlation"], indent=2))
    print(f"wrote {csv_path}")
    print(f"wrote {fig_path}")
    print(f"wrote {summary_path}")


if __name__ == "__main__":
    main()
