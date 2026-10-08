#!/usr/bin/env python3
"""Phase 8b: run Full DoD EDA against DWH and write artifacts + findings.

Example:
    py -3 scripts/run_eda_phase8b.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from src.eda import analysis as eda  # noqa: E402

OUT = ROOT / "artifacts" / "eda"
FIGS = OUT / "figures"


def _save_csv(df: pd.DataFrame, name: str) -> Path:
    path = OUT / name
    df.to_csv(path, index=False)
    return path


def _save_fig(name: str) -> Path:
    FIGS.mkdir(parents=True, exist_ok=True)
    path = FIGS / name
    plt.tight_layout()
    plt.savefig(path, dpi=120)
    plt.close()
    return path


def _json_ready(value):
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat(sep=" ")
    # Decimal / numpy scalars
    try:
        from decimal import Decimal

        if isinstance(value, Decimal):
            return float(value)
    except Exception:
        pass
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    if isinstance(value, (float, int, str, bool)):
        return value
    try:
        return float(value)
    except Exception:
        return str(value)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    FIGS.mkdir(parents=True, exist_ok=True)

    # --- Temporal ---
    by_hour = eda.pm25_by_hour_of_day()
    by_month = eda.pm25_by_month()
    by_season = eda.pm25_by_season()
    by_year = eda.pm25_by_year()
    pm25_pct = eda.global_pm25_percentiles()
    _save_csv(by_hour, "temporal_pm25_by_hour.csv")
    _save_csv(by_month, "temporal_pm25_by_month.csv")
    _save_csv(by_season, "temporal_pm25_by_season.csv")
    _save_csv(by_year, "temporal_pm25_by_year.csv")

    plt.figure(figsize=(8, 4))
    plt.plot(by_hour["hour_of_day"], by_hour["pm25_avg"], marker="o")
    plt.xlabel("Hour of day")
    plt.ylabel("PM2.5 avg (µg/m³)")
    plt.title("PM2.5 by hour of day")
    plt.grid(True, alpha=0.3)
    _save_fig("temporal_pm25_by_hour.png")

    plt.figure(figsize=(8, 4))
    order = ["winter", "spring", "summer", "autumn"]
    season_plot = by_season.set_index("season").reindex(order)
    plt.bar(season_plot.index.astype(str), season_plot["pm25_avg"])
    plt.ylabel("PM2.5 avg (µg/m³)")
    plt.title("PM2.5 by season")
    _save_fig("temporal_pm25_by_season.png")

    # --- Station ---
    stations = eda.station_pm25_summary()
    peaks = eda.station_peak_days(20)
    _save_csv(stations, "station_pm25_summary.csv")
    _save_csv(peaks, "station_peak_days.csv")

    plt.figure(figsize=(10, 5))
    plt.barh(stations["station_name"][::-1], stations["pm25_mean"][::-1])
    plt.xlabel("PM2.5 mean (µg/m³)")
    plt.title("Station ranking by mean PM2.5")
    _save_fig("station_pm25_ranking.png")

    # --- Pollutant ---
    poll_summary = eda.pollutant_overall_summary()
    poll_season = eda.pollutant_by_season()
    poll_sample = eda.pollutant_correlation_sample()
    corr = poll_sample.corr(numeric_only=True).round(3)
    _save_csv(poll_summary, "pollutant_summary.csv")
    _save_csv(poll_season, "pollutant_by_season.csv")
    corr.to_csv(OUT / "pollutant_correlation.csv")

    plt.figure(figsize=(6, 5))
    im = plt.imshow(corr.values, cmap="coolwarm", vmin=-1, vmax=1)
    plt.colorbar(im, fraction=0.046)
    labels = list(corr.columns)
    plt.xticks(range(len(labels)), labels, rotation=45, ha="right")
    plt.yticks(range(len(labels)), labels)
    plt.title("Pollutant correlation (sample)")
    _save_fig("pollutant_correlation.png")

    # --- Weather ---
    temp_bins = eda.weather_vs_pm25_bins()
    wind_bins = eda.weather_vs_pm25_wind()
    rh_bins = eda.weather_vs_pm25_rh()
    wx_sample = eda.weather_pm25_correlations()
    wx_corr = (
        wx_sample.corr(numeric_only=True)["pm25_ug_m3"]
        .drop(labels=["pm25_ug_m3"])
        .sort_values()
        .round(3)
    )
    _save_csv(temp_bins, "weather_pm25_by_temp_bin.csv")
    _save_csv(wind_bins, "weather_pm25_by_wind_bin.csv")
    _save_csv(rh_bins, "weather_pm25_by_rh_bin.csv")
    wx_corr.to_csv(OUT / "weather_pm25_correlation.csv", header=["corr_with_pm25"])

    plt.figure(figsize=(8, 4))
    plt.plot(temp_bins["temp_avg"], temp_bins["pm25_avg"], marker="o")
    plt.xlabel("Temperature avg in bin (°C)")
    plt.ylabel("PM2.5 avg (µg/m³)")
    plt.title("PM2.5 vs temperature bins")
    plt.grid(True, alpha=0.3)
    _save_fig("weather_pm25_vs_temp.png")

    plt.figure(figsize=(8, 4))
    plt.plot(wind_bins["wind_avg"], wind_bins["pm25_avg"], marker="o")
    plt.xlabel("Wind speed avg in bin (m/s)")
    plt.ylabel("PM2.5 avg (µg/m³)")
    plt.title("PM2.5 vs wind speed bins")
    plt.grid(True, alpha=0.3)
    _save_fig("weather_pm25_vs_wind.png")

    # --- Data issues ---
    dq = eda.data_quality_overview()
    missing = eda.missing_rates_by_station()
    wx_src = eda.weather_source_mix()
    _save_csv(dq, "dq_status_overview.csv")
    _save_csv(missing, "missing_rates_by_station.csv")
    _save_csv(wx_src, "weather_temperature_source_mix.csv")

    summary = {
        "pm25_global_percentiles": {k: _json_ready(v) for k, v in pm25_pct.items()},
        "season_highest_pm25": by_season.sort_values("pm25_avg", ascending=False)
        .iloc[0][["season", "pm25_avg", "pm25_p90"]]
        .to_dict(),
        "hour_peak": by_hour.sort_values("pm25_avg", ascending=False).iloc[0].to_dict(),
        "hour_trough": by_hour.sort_values("pm25_avg", ascending=True).iloc[0].to_dict(),
        "dirtiest_station": stations.iloc[0][["station_name", "pm25_mean", "pm25_p95"]].to_dict(),
        "cleanest_station": stations.iloc[-1][["station_name", "pm25_mean", "pm25_p95"]].to_dict(),
        "weather_corr_with_pm25": {k: _json_ready(v) for k, v in wx_corr.items()},
        "pollutant_corr_pm25": {
            k: _json_ready(v)
            for k, v in corr["pm25_ug_m3"].drop(labels=["pm25_ug_m3"]).items()
        },
    }
    for block in ("season_highest_pm25", "hour_peak", "hour_trough", "dirtiest_station", "cleanest_station"):
        summary[block] = {k: _json_ready(v) for k, v in summary[block].items()}

    (OUT / "eda_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    findings = _build_findings(summary, by_season, by_year, stations, poll_summary, dq, missing, wx_src)
    (OUT / "eda_findings.md").write_text(findings, encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "artifacts_dir": str(OUT),
                "findings": str(OUT / "eda_findings.md"),
                "summary": str(OUT / "eda_summary.json"),
            },
            ensure_ascii=False,
        )
    )
    return 0


def _build_findings(
    summary: dict,
    by_season: pd.DataFrame,
    by_year: pd.DataFrame,
    stations: pd.DataFrame,
    poll_summary: pd.DataFrame,
    dq: pd.DataFrame,
    missing: pd.DataFrame,
    wx_src: pd.DataFrame,
) -> str:
    pct = summary["pm25_global_percentiles"]
    season_lines = "\n".join(
        f"- **{r.season}**: mean {r.pm25_avg}, P90 {r.pm25_p90}, P95 {r.pm25_p95}"
        for r in by_season.itertuples()
    )
    year_lines = "\n".join(
        (
            f"- **{int(r.year)}**: mean {r.pm25_avg}, P90 {r.pm25_p90}"
            + (" *(partial year: Jan–Feb only → winter-biased)*" if int(r.year) == 2017 else "")
        )
        for r in by_year.itertuples()
    )
    station_top = "\n".join(
        f"- {r.station_name}: mean {r.pm25_mean}, median {r.pm25_median}, P95 {r.pm25_p95}"
        for r in stations.head(5).itertuples()
    )
    station_bot = "\n".join(
        f"- {r.station_name}: mean {r.pm25_mean}, median {r.pm25_median}, P95 {r.pm25_p95}"
        for r in stations.tail(3).itertuples()
    )
    poll_lines = "\n".join(
        f"- **{r.pollutant}**: mean {r.mean_val}, P90 {r.p90}, P95 {r.p95}, n={int(r.n_non_null)}"
        for r in poll_summary.itertuples()
    )
    wx_corr = summary["weather_corr_with_pm25"]
    wx_lines = "\n".join(f"- {k}: {v}" for k, v in sorted(wx_corr.items(), key=lambda x: x[1]))
    poll_corr = summary["pollutant_corr_pm25"]
    pc_lines = "\n".join(
        f"- {k}: {v}" for k, v in sorted(poll_corr.items(), key=lambda x: -abs(x[1]))
    )
    dq_lines = "\n".join(
        f"- `{r.data_quality_status}`: {int(r.row_count)} rows ({r.pct}%)"
        for r in dq.itertuples()
    )
    miss_top = missing.sort_values("pm25_missing_pct", ascending=False).head(3)
    miss_lines = "\n".join(
        f"- {r.station_name}: PM2.5 missing {r.pm25_missing_pct}%, weather missing {r.weather_missing_pct}%"
        for r in miss_top.itertuples()
    )
    src_lines = "\n".join(
        f"- temperature_source=`{r.temperature_source}`: {int(r.n)} ({r.pct}%)"
        for r in wx_src.itertuples()
    )
    peak = summary["hour_peak"]
    trough = summary["hour_trough"]

    return f"""# Phase 8b – EDA findings (from DWH)

Source: `dwh.fact_air_quality_hourly` + dims/marts. Generated by `scripts/run_eda_phase8b.py`.

## Temporal

Global PM2.5 (non-null hours): mean **{pct['mean_val']}**, P50 **{pct['p50']}**, P75 **{pct['p75']}**, P90 **{pct['p90']}**, P95 **{pct['p95']}** (n={int(pct['n'])}).

### By season
{season_lines}

### By year
{year_lines}

### Diurnal
- Peak hour: **{int(peak['hour_of_day'])}:00** (avg {peak['pm25_avg']})
- Trough hour: **{int(trough['hour_of_day'])}:00** (avg {trough['pm25_avg']})

**Insight:** Winter (and cold months) dominate high PM2.5; summer is markedly cleaner. Diurnal swing exists but is smaller than seasonal contrast — useful calendar features for ML.

## Station

Dirtiest by mean: **{summary['dirtiest_station']['station_name']}** ({summary['dirtiest_station']['pm25_mean']}).  
Cleanest by mean: **{summary['cleanest_station']['station_name']}** ({summary['cleanest_station']['pm25_mean']}).

### Top 5 (mean PM2.5)
{station_top}

### Bottom 3
{station_bot}

**Insight:** Station ranking is stable enough for clustering (Phase 9) and for station identity / district as features. Peak pollution days cluster in winter months (see `station_peak_days.csv`).

## Pollutant suite

{poll_lines}

### Correlation with PM2.5 (sample)
{pc_lines}

**Insight:** PM10 and combustion-related gases (NO2/CO/SO2) move with PM2.5; O3 tends to diverge (photochemistry). Target stays PM2.5; others are supporting features, not alternate targets in Phase 10.

## Weather relationships (pattern only — not causal)

### Correlation with PM2.5 (sample)
{wx_lines}

Binned views: colder temperature bins and weaker wind bins show higher average PM2.5 (`weather_pm25_by_*_bin.csv`, figures under `figures/`).

**Insight:** Temperature, wind speed, and humidity show the clearest co-variation with PM2.5 among resolved weather fields. Prefer **lagged / prior-hour** weather in forecasting to avoid same-hour leakage.

## Data issues noted in Phase 8

### Fact `data_quality_status`
{dq_lines}

### Highest PM2.5 missing rates
{miss_lines}

### Temperature source mix (UCI vs Open-Meteo fill)
{src_lines}

**Insight:** Missing PM2.5 is a few percent overall but uneven by station — episode detection must **cut on null** (already decided). Weather after Phase 7 resolve is largely complete via Open-Meteo fill; keep `*_source` flags if models need quality awareness.

## Artifacts

- CSV tables under `artifacts/eda/`
- Figures under `artifacts/eda/figures/`
- Machine summary: `artifacts/eda/eda_summary.json`

## Next (P8c)

Use global P90/P95 above plus fixed **75** / **115** in the episode sensitivity grid; lock definition in `episode_definition.md`.
"""


if __name__ == "__main__":
    raise SystemExit(main())
