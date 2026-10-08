#!/usr/bin/env python3
"""Write Phase 8b exploratory notebooks (no jupyter required to generate)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "notebooks" / "eda"

SETUP = """\
from pathlib import Path
import sys
ROOT = Path.cwd()
if not (ROOT / "src").exists():
    ROOT = Path.cwd().parents[1]  # when kernel cwd is notebooks/eda
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass
"""


def nb(cells: list[tuple[str, str]]) -> dict:
    out_cells = []
    for kind, source in cells:
        src = source if source.endswith("\n") else source + "\n"
        lines = src.splitlines(keepends=True)
        if kind == "markdown":
            out_cells.append({"cell_type": "markdown", "metadata": {}, "source": lines})
        else:
            out_cells.append(
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": lines,
                }
            )
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "cells": out_cells,
    }


NOTEBOOKS = {
    "05_episodes_sensitivity.ipynb": [
        (
            "markdown",
            "# P8c – Episode sensitivity\n\n"
            "Prefer batch: `py -3 scripts/run_eda_phase8c.py` → "
            "`artifacts/eda/episode_definition.md`.",
        ),
        (
            "code",
            SETUP
            + "\nfrom src.eda import episodes as ep\n"
            "df = ep.load_hourly_frame()\ngrid = ep.sensitivity_grid(df)\ngrid",
        ),
    ],
    "06_episodes_analysis.ipynb": [
        (
            "markdown",
            "# P8c – Locked episode analysis\n\n"
            "Locked rule: see `artifacts/eda/episode_definition.md` "
            "(115 µg/m³, min 3h, multi-station K=6).",
        ),
        (
            "code",
            SETUP
            + "\nimport pandas as pd\n"
            "from pathlib import Path\n"
            "ROOT = Path.cwd() if (Path.cwd() / 'artifacts').exists() else Path.cwd().parents[1]\n"
            "pd.read_csv(ROOT / 'artifacts/eda/episodes_station_stats_locked.csv')",
        ),
        (
            "code",
            "pd.read_csv(ROOT / 'artifacts/eda/episodes_multi_station_locked.csv').head(20)",
        ),
    ],
    "01_temporal.ipynb": [
        ("markdown", "# P8b – Temporal EDA\n\nPM2.5 by hour / month / season / year from `dwh.fact_air_quality_hourly`."),
        ("code", SETUP + "\nfrom src.eda import analysis as eda\nimport matplotlib.pyplot as plt\n"),
        ("code", "eda.pm25_by_season()"),
        ("code", "eda.pm25_by_year()"),
        ("code", "by_hour = eda.pm25_by_hour_of_day()\nby_hour"),
        (
            "code",
            "plt.figure(figsize=(8,4))\nplt.plot(by_hour['hour_of_day'], by_hour['pm25_avg'], marker='o')\n"
            "plt.xlabel('Hour'); plt.ylabel('PM2.5 avg'); plt.grid(True, alpha=0.3); plt.show()",
        ),
        ("markdown", "Or regenerate all artifacts: `py -3 scripts/run_eda_phase8b.py`"),
    ],
    "02_station.ipynb": [
        ("markdown", "# P8b – Station EDA\n\nMean / median / variance / peaks / ranking across 12 stations."),
        ("code", SETUP + "\nfrom src.eda import analysis as eda\n"),
        ("code", "stations = eda.station_pm25_summary()\nstations"),
        ("code", "eda.station_peak_days(20)"),
    ],
    "03_pollutant.ipynb": [
        ("markdown", "# P8b – Pollutant suite\n\nPM2.5, PM10, SO₂, NO₂, CO, O₃ summaries and correlations."),
        ("code", SETUP + "\nfrom src.eda import analysis as eda\n"),
        ("code", "eda.pollutant_overall_summary()"),
        ("code", "eda.pollutant_by_season().head(24)"),
        ("code", "sample = eda.pollutant_correlation_sample()\nsample.corr(numeric_only=True).round(3)"),
    ],
    "04_weather.ipynb": [
        ("markdown", "# P8b – Weather vs PM2.5\n\nPattern only — not causal. Prefer lagged weather for forecasting."),
        ("code", SETUP + "\nfrom src.eda import analysis as eda\n"),
        ("code", "eda.weather_vs_pm25_bins()"),
        ("code", "eda.weather_vs_pm25_wind()"),
        ("code", "eda.weather_vs_pm25_rh()"),
        (
            "code",
            "wx = eda.weather_pm25_correlations()\n"
            "wx.corr(numeric_only=True)['pm25_ug_m3'].drop('pm25_ug_m3').sort_values()",
        ),
    ],
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, cells in NOTEBOOKS.items():
        path = OUT / name
        path.write_text(json.dumps(nb(cells), indent=1) + "\n", encoding="utf-8")
        print(path)


if __name__ == "__main__":
    main()
