#!/usr/bin/env python3
"""Phase 10e: error analysis + optional 2017 sensitivity + docs sync notes.

Example:
    py -3 scripts/run_forecasting_phase10e.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from src.forecasting.constants import FEATURE_COLS, TARGET_COL  # noqa: E402
from src.forecasting.error_analysis import (  # noqa: E402
    build_error_report_tables,
    load_predictions_with_names,
    overall_test_metrics,
)
from src.forecasting.extract import fetch_forecast_base  # noqa: E402
from src.forecasting.features import (  # noqa: E402
    add_calendar_codes,
    add_pm25_lags_and_rolls,
    add_target,
    add_weather_lags_and_missing_flags,
    drop_unusable_rows,
    impute_weather_from_train,
)
from src.forecasting.metrics import regression_metrics  # noqa: E402
from src.forecasting.models import HISTGB_CAT_COLS, predict_persistence  # noqa: E402

OUT = ROOT / "artifacts" / "forecasting"
FIGS = OUT / "figures"
LOCK = OUT / "model_lock.json"
MODEL = ROOT / "models" / "pm25_forecast" / "model.joblib"


def _savefig(fig, name: str) -> str:
    FIGS.mkdir(parents=True, exist_ok=True)
    path = FIGS / name
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return str(path.relative_to(ROOT)).replace("\\", "/")


def _plot_station_mae(by_station: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(9, 4.5))
    s = by_station.sort_values("mae")
    ax.barh(s["station_name"], s["mae"], color="#4C78A8", label="HistGB")
    ax.plot(s["mae_persistence"], s["station_name"], "o", color="#F58518", label="Persistence")
    ax.set_xlabel("Test MAE (µg/m³)")
    ax.set_title("Test MAE by station (locked HistGB vs persistence)")
    ax.legend(loc="lower right")
    return _savefig(fig, "error_mae_by_station.png")


def _plot_hour_mae(by_hour: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(8, 3.5))
    h = by_hour.sort_values("hour")
    ax.plot(h["hour"], h["mae"], marker="o", label="HistGB")
    ax.plot(h["hour"], h["mae_persistence"], marker="o", label="Persistence")
    ax.set_xlabel("Hour of day")
    ax.set_ylabel("Test MAE")
    ax.set_title("Test MAE by hour")
    ax.set_xticks(range(0, 24, 2))
    ax.legend()
    return _savefig(fig, "error_mae_by_hour.png")


def _plot_residual_scatter(test: pd.DataFrame, *, max_points: int = 8000) -> str:
    sample = test
    if len(sample) > max_points:
        sample = sample.sample(max_points, random_state=42)
    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    ax.scatter(sample[TARGET_COL], sample["y_hat_locked"], s=6, alpha=0.25, c="#4C78A8")
    lim = float(max(sample[TARGET_COL].max(), sample["y_hat_locked"].max()))
    ax.plot([0, lim], [0, lim], "k--", lw=1)
    ax.set_xlabel("Actual PM2.5 (t+1)")
    ax.set_ylabel("Predicted PM2.5")
    ax.set_title("Test: actual vs predicted (sample)")
    return _savefig(fig, "error_actual_vs_pred.png")


def _plot_residual_by_bin(bins: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(8, 3.8))
    ax.bar(range(len(bins)), bins["mae"], color="#54A24B")
    ax.set_xticks(range(len(bins)))
    ax.set_xticklabels(bins["actual_bin"], rotation=30, ha="right")
    ax.set_ylabel("MAE")
    ax.set_title("Test MAE by actual PM2.5 bin")
    return _savefig(fig, "error_mae_by_actual_bin.png")


def run_2017_sensitivity() -> dict:
    """Score locked model on 2017-01..02 (winter-biased); not part of primary DoD."""
    try:
        base = fetch_forecast_base(start="2016-12-01 00:00:00", end="2017-02-28 23:00:00")
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}

    df = base.sort_values(["station_key", "event_time_local"]).reset_index(drop=True)
    df = add_calendar_codes(df)
    df = add_pm25_lags_and_rolls(df)
    df = add_weather_lags_and_missing_flags(df)
    df = add_target(df)
    # Dec 2016 = warm-up / train-median only; score Jan–Feb 2017
    df["split"] = np.where(
        df["event_time_local"] < pd.Timestamp("2017-01-01"),
        "train",
        "test",
    )
    df = drop_unusable_rows(df)
    df, medians = impute_weather_from_train(df)
    df = df[df["event_time_local"] >= pd.Timestamp("2017-01-01")].reset_index(drop=True)
    if df.empty:
        return {"ok": False, "error": "no 2017 rows after feature drop"}

    bundle = joblib.load(MODEL)
    est = bundle["estimator"]
    x = df.loc[:, list(FEATURE_COLS)].copy()
    for c in HISTGB_CAT_COLS:
        if c in x.columns:
            x[c] = x[c].astype(int)
    preds = est.predict(x)
    base_preds = predict_persistence(df)
    locked_m = regression_metrics(df[TARGET_COL], preds)
    pers_m = regression_metrics(df[TARGET_COL], base_preds)
    return {
        "ok": True,
        "note": "2017 Jan–Feb only (winter-biased); not primary DoD",
        "n": int(len(df)),
        "weather_medians_from": "2016-12 warm-up",
        "weather_medians": medians,
        "locked": locked_m,
        "persistence": pers_m,
        "beats_persistence": locked_m["mae"] < pers_m["mae"],
    }


def write_markdown(
    metrics: dict,
    tables: dict[str, pd.DataFrame],
    figures: dict[str, str],
    sens2017: dict,
) -> str:
    by_st = tables["test_by_station"].sort_values("mae")
    best = by_st.iloc[0]
    worst = by_st.iloc[-1]
    by_cl = tables["test_by_cluster"]
    by_season = tables["test_by_season"].sort_values("mae")
    worst_days = tables["test_worst_days"].head(8)

    lines = [
        "# Phase 10e – Forecast error analysis",
        "",
        "**Locked model:** HistGradientBoosting (global, PM2.5 t+1h)  ",
        "**Primary test:** 2016-07-01 → 2016-12-31  ",
        f"**Test n:** {metrics['n_test']:,}",
        "",
        "## Overall (test)",
        "",
        "| Model | MAE | RMSE | R² |",
        "|-------|-----|------|----|",
        f"| Persistence | {metrics['persistence']['mae']:.3f} | {metrics['persistence']['rmse']:.3f} | {metrics['persistence']['r2']:.4f} |",
        f"| **HistGB (locked)** | **{metrics['locked']['mae']:.3f}** | **{metrics['locked']['rmse']:.3f}** | **{metrics['locked']['r2']:.4f}** |",
        "",
        f"MAE lift vs persistence: **{metrics['mae_lift']:.3f}** µg/m³ "
        f"({100 * metrics['mae_lift'] / metrics['persistence']['mae']:.1f}% relative).",
        "",
        "## By station (test)",
        "",
        f"- Best MAE: **{best['station_name']}** ({best['mae']:.2f}) — cluster `{best['cluster_label']}`",
        f"- Worst MAE: **{worst['station_name']}** ({worst['mae']:.2f}) — cluster `{worst['cluster_label']}`",
        "",
        "Full table: `error_by_station_test.csv`.",
        "",
        f"![MAE by station](figures/{Path(figures['station']).name})",
        "",
        "## By cluster (test)",
        "",
        "| cluster | label | n | MAE | Persistence MAE | Lift |",
        "|---------|-------|---|-----|-----------------|------|",
    ]
    for _, r in by_cl.iterrows():
        lines.append(
            f"| {int(r['cluster_id'])} | `{r['cluster_label']}` | {int(r['n'])} | "
            f"{r['mae']:.2f} | {r['mae_persistence']:.2f} | {r['mae_lift_vs_persistence']:.2f} |"
        )

    lines += [
        "",
        "## By season (test)",
        "",
        "| season | n | MAE | Persistence MAE |",
        "|--------|---|-----|-----------------|",
    ]
    for _, r in by_season.iterrows():
        lines.append(
            f"| {r['season']} | {int(r['n'])} | {r['mae']:.2f} | {r['mae_persistence']:.2f} |"
        )

    lines += [
        "",
        f"![MAE by hour](figures/{Path(figures['hour']).name})",
        "",
        f"![Actual vs pred](figures/{Path(figures['scatter']).name})",
        "",
        f"![MAE by actual bin](figures/{Path(figures['bins']).name})",
        "",
        "## Where errors hurt most",
        "",
        "- Absolute error grows with **high actual PM2.5** (episode / pollution peaks) — "
        "see `error_residual_by_actual_bin_test.csv`.",
        "- Persistence remains strong hour-to-hour; HistGB gain is largest where weather / "
        "lags / station structure add signal beyond lag-1.",
        "",
        "### Worst station-days (test, by mean abs error)",
        "",
        "| day | station | MAE | max\\|err\\| | mean actual |",
        "|-----|---------|-----|-----------|-------------|",
    ]
    for _, r in worst_days.iterrows():
        lines.append(
            f"| {pd.Timestamp(r['day']).date()} | {r['station_name']} | "
            f"{r['mae']:.1f} | {r['max_abs_error']:.1f} | {r['mean_actual']:.1f} |"
        )

    lines += [
        "",
        "## 2017 sensitivity (optional, not DoD)",
        "",
    ]
    if sens2017.get("ok"):
        lines += [
            sens2017.get("note", ""),
            "",
            f"- n = {sens2017['n']:,}",
            f"- HistGB MAE = **{sens2017['locked']['mae']:.3f}**",
            f"- Persistence MAE = **{sens2017['persistence']['mae']:.3f}**",
            f"- Beats persistence: **{sens2017['beats_persistence']}**",
            "",
            "Interpret cautiously: Jan–Feb 2017 is winter-only and short.",
        ]
    else:
        lines.append(f"_Skipped / failed:_ `{sens2017.get('error', sens2017)}`")

    lines += [
        "",
        "## Artifacts",
        "",
        "- `error_by_*.csv`, `error_worst_days_test.csv`",
        "- `error_analysis.md` (this file)",
        "- figures under `artifacts/forecasting/figures/`",
        "- mart: `mart.mart_pm25_predictions`",
        "",
    ]
    path = OUT / "error_analysis.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path.relative_to(ROOT)).replace("\\", "/")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    FIGS.mkdir(parents=True, exist_ok=True)

    try:
        df = load_predictions_with_names()
        tables = build_error_report_tables(df)
        metrics = overall_test_metrics(df)
        test = df[df["split"] == "test"]

        for name, table in tables.items():
            table.to_csv(OUT / f"error_{name}.csv", index=False)

        figures = {
            "station": _plot_station_mae(tables["test_by_station"]),
            "hour": _plot_hour_mae(tables["test_by_hour"]),
            "scatter": _plot_residual_scatter(test),
            "bins": _plot_residual_by_bin(tables["test_residual_by_actual_bin"]),
        }

        sens2017 = run_2017_sensitivity()
        (OUT / "sensitivity_2017.json").write_text(
            json.dumps(sens2017, indent=2) + "\n", encoding="utf-8"
        )

        md = write_markdown(metrics, tables, figures, sens2017)

        summary = {
            "ok": True,
            "phase": "P10e",
            "test_metrics": metrics,
            "figures": figures,
            "error_analysis_md": md,
            "sensitivity_2017": sens2017,
            "csv_prefix": "artifacts/forecasting/error_",
        }
        path = OUT / "error_analysis_summary.json"
        path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False))
        return 0
    except Exception as exc:  # noqa: BLE001
        report = {"ok": False, "phase": "P10e", "error": str(exc)}
        (OUT / "error_analysis_summary.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(report, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
