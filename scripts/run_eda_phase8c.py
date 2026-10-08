#!/usr/bin/env python3
"""Phase 8c: episode sensitivity grid, lock definition, locked analyses.

Example:
    py -3 scripts/run_eda_phase8c.py
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

from src.eda import episodes as ep  # noqa: E402

OUT = ROOT / "artifacts" / "eda"
FIGS = OUT / "figures"


def _json_ready(value):
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat(sep=" ")
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


def _clean(obj):
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean(v) for v in obj]
    return _json_ready(obj)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    FIGS.mkdir(parents=True, exist_ok=True)

    print("loading fact...", flush=True)
    df = ep.load_hourly_frame()
    pct = ep.global_percentile_thresholds(df)
    print(f"rows={len(df)} p90={pct['P90']:.1f} p95={pct['P95']:.1f}", flush=True)

    print("sensitivity grid...", flush=True)
    grid = ep.sensitivity_grid(df)
    grid_path = OUT / "episode_sensitivity_grid.csv"
    grid.to_csv(grid_path, index=False)

    # Lock using concurrent dist at preferred 115 / 3h
    print("locking rule...", flush=True)
    concurrent = ep.concurrent_distribution(df, threshold=115.0, min_hours=3)
    concurrent.to_csv(OUT / "episode_concurrent_dist_115_3h.csv", index=False)
    rule = ep.choose_locked_rule(concurrent)

    # Locked analyses
    print("locked station episodes...", flush=True)
    station_eps = ep.detect_station_episodes(df, rule.threshold_ug_m3, rule.min_hours)
    station_eps.to_csv(OUT / "episodes_station_locked.csv", index=False)
    station_stats = ep.station_episode_stats(station_eps)
    station_stats.to_csv(OUT / "episodes_station_stats_locked.csv", index=False)

    print("locked multi-station...", flush=True)
    counts = ep.hourly_station_counts(df, rule.threshold_ug_m3, rule.min_hours)
    counts.to_csv(OUT / "episode_hourly_station_counts_locked.csv", index=False)
    multi = ep.detect_multi_station_events(counts, rule.multi_station_k)
    multi.to_csv(OUT / "episodes_multi_station_locked.csv", index=False)

    print("weather in episode...", flush=True)
    weather = ep.weather_episode_vs_baseline(df, rule.threshold_ug_m3, rule.min_hours)

    # Figures
    plt.figure(figsize=(10, 5))
    pivot = grid.pivot_table(
        index="threshold_label", columns="min_hours", values="episode_count"
    )
    pivot.plot(kind="bar", ax=plt.gca())
    plt.ylabel("Station-episode count")
    plt.title("Sensitivity: episode count by threshold × min_hours")
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    plt.savefig(FIGS / "episode_sensitivity_counts.png", dpi=120)
    plt.close()

    if not station_stats.empty:
        plt.figure(figsize=(10, 5))
        ordered = station_stats.sort_values("episode_count")
        plt.barh(ordered["station_name"], ordered["episode_count"])
        plt.xlabel("Episode count")
        plt.title(
            f"Station episodes (PM2.5>={rule.threshold_ug_m3:g}, min {rule.min_hours}h)"
        )
        plt.tight_layout()
        plt.savefig(FIGS / "episode_station_counts_locked.png", dpi=120)
        plt.close()

    if not concurrent.empty:
        plt.figure(figsize=(8, 4))
        plt.bar(concurrent["n_stations"].astype(str), concurrent["hour_count"])
        plt.xlabel("Stations in episode (same hour)")
        plt.ylabel("Hour count")
        plt.title("Concurrent station distribution (115 / 3h)")
        plt.tight_layout()
        plt.savefig(FIGS / "episode_concurrent_dist.png", dpi=120)
        plt.close()

    summary = {
        "percentiles": pct,
        "locked_rule": rule.to_dict(),
        "locked_station_episode_summary": ep.summarize_station_episodes(station_eps),
        "locked_multi_station_event_count": int(len(multi)),
        "locked_multi_duration_median": (
            float(multi["duration_hours"].median()) if not multi.empty else None
        ),
        "weather_episode_vs_baseline": weather,
        "concurrent_pct_hours_ge_k": {
            str(k): round(
                100.0
                * float(concurrent.loc[concurrent["n_stations"] >= k, "hour_count"].sum())
                / float(concurrent["hour_count"].sum()),
                2,
            )
            for k in ep.K_GRID
        },
    }
    (OUT / "episode_lock_summary.json").write_text(
        json.dumps(_clean(summary), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    definition = _build_definition(summary, grid, station_stats, multi, concurrent)
    (OUT / "episode_definition.md").write_text(definition, encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "locked_rule": rule.to_dict(),
                "definition": str(OUT / "episode_definition.md"),
                "grid": str(grid_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


def _r(value, digits: int = 2):
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except Exception:
        return value


def _build_definition(
    summary: dict,
    grid: pd.DataFrame,
    station_stats: pd.DataFrame,
    multi: pd.DataFrame,
    concurrent: pd.DataFrame,
) -> str:
    rule = summary["locked_rule"]
    st = summary["locked_station_episode_summary"]
    wx = summary["weather_episode_vs_baseline"]
    pct = summary["percentiles"]
    ge = summary["concurrent_pct_hours_ge_k"]

    grid_lines = []
    for r in grid.itertuples():
        grid_lines.append(
            f"| {r.threshold_label} | {r.min_hours} | {int(r.episode_count)} | "
            f"{r.duration_median} | {r.duration_p90} | {int(r.multi_events_k3)} / "
            f"{int(r.multi_events_k6)} / {int(r.multi_events_k9)} |"
        )
    grid_table = "\n".join(grid_lines)

    top_stations = ""
    if not station_stats.empty:
        top_stations = "\n".join(
            f"- {r.station_name}: {int(r.episode_count)} episodes, "
            f"median duration {r.duration_median:.1f}h"
            for r in station_stats.head(5).itertuples()
        )

    ep_wx = wx.get("episode", {})
    base_wx = wx.get("baseline", {})

    return f"""# Phase 8c – PM2.5 episode definition (LOCKED)

## Locked rule (use in dbt marts / P8d)

| Parameter | Value | Why |
|-----------|-------|-----|
| `threshold_ug_m3` | **{rule['threshold_ug_m3']:g}** | Near global P75≈111; marks *elevated* hours, not the long-run mean (~80). More selective than 75; less extreme-only than P90≈{pct['P90']:.0f}. |
| `min_hours` | **{rule['min_hours']}** | Drops one-hour spikes; sensitivity shows 1h inflates counts heavily vs 3h. |
| `multi_station_k` | **{rule['multi_station_k']}** | Network is highly coherent (n≥3 already ~{ge['3']}% of hours; n=12 alone common). **K=6** = half of 12 stations marks *regional* events without requiring near city-wide. |
| Null handling | **cut** | Null PM2.5 is not dirty and breaks a run (no bridging). |

Global reference percentiles (hourly non-null PM2.5): P90={pct['P90']:.1f}, P95={pct['P95']:.1f}.

### Concurrent rarity under locked 115 / 3h

- Hours with n≥3: **{ge['3']}%**
- Hours with n≥6: **{ge['6']}%**
- Hours with n≥9: **{ge['9']}%**

## Formal definition

1. A station-hour is **dirty** iff `pm25_ug_m3 >= {rule['threshold_ug_m3']:g}` (null ⇒ not dirty).
2. A **station episode** is a maximal run of consecutive dirty hours at one station with length `>= {rule['min_hours']}`.
3. For each timestamp, `n_stations_in_episode` = count of stations whose hour belongs to a station episode.
4. A **multi-station event** is a maximal run of hours with `n_stations_in_episode >= {rule['multi_station_k']}`.

Not a realtime detector — historical analytics only.

## Sensitivity grid (summary)

| threshold | min_h | episodes | dur_median | dur_p90 | multi events K=3/6/9 |
|-----------|------:|---------:|-----------:|--------:|----------------------|
{grid_table}

Full CSV: `artifacts/eda/episode_sensitivity_grid.csv`.

## Locked results (quick)

- Station episodes: **{st['episode_count']}** across **{st['stations_with_episodes']}** stations
- Duration hours: median **{st['duration_median']}**, P90 **{st['duration_p90']}**, mean **{st['duration_mean']:.2f}**
- By season: `{st['by_season']}`
- By year: `{st['by_year']}`
- Multi-station events (K={rule['multi_station_k']}): **{summary['locked_multi_station_event_count']}** (median duration {summary['locked_multi_duration_median']} h)

### Top stations by episode count
{top_stations}

## Weather inside episodes vs baseline (pattern only)

Episode hours: {wx.get('episode_hours')}; baseline hours: {wx.get('baseline_hours')}.

| Metric | Inside episode | Baseline |
|--------|----------------|----------|
| PM2.5 avg | {_r(ep_wx.get('pm25_ug_m3_avg'))} | {_r(base_wx.get('pm25_ug_m3_avg'))} |
| Temp °C | {_r(ep_wx.get('temperature_c_avg'))} | {_r(base_wx.get('temperature_c_avg'))} |
| RH % | {_r(ep_wx.get('relative_humidity_pct_avg'))} | {_r(base_wx.get('relative_humidity_pct_avg'))} |
| Wind m/s | {_r(ep_wx.get('wind_speed_m_s_avg'))} | {_r(base_wx.get('wind_speed_m_s_avg'))} |
| Rain mm (mean hour) | {_r(ep_wx.get('rain_mm_mean'), 3)} | {_r(base_wx.get('rain_mm_mean'), 3)} |
| Cloud % | {_r(ep_wx.get('cloud_cover_pct_avg'))} | {_r(base_wx.get('cloud_cover_pct_avg'))} |

Interpretation: descriptive co-occurrence only — do **not** claim causality.

## Artifacts for P8d

- `episodes_station_locked.csv` — grain preview for `mart_pm25_episodes`
- `episodes_multi_station_locked.csv` — grain preview for `mart_pm25_multi_station_events`
- `episode_lock_summary.json` — machine-readable lock + summaries
- dbt vars to set: `pm25_episode_threshold={rule['threshold_ug_m3']:g}`, `pm25_episode_min_hours={rule['min_hours']}`, `pm25_multi_station_k={rule['multi_station_k']}`
"""


if __name__ == "__main__":
    raise SystemExit(main())
