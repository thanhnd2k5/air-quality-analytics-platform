#!/usr/bin/env python3
"""Vòng B LSTM: error analysis vs persistence / HistGB v2 (no production overwrite).

Example:
    py -3 scripts/run_forecasting_lstm_c.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from src.forecasting.constants import TARGET_COL  # noqa: E402
from src.forecasting.error_analysis import (  # noqa: E402
    build_error_report_tables,
    load_predictions_with_names,
    overall_test_metrics,
)

OUT = ROOT / "artifacts" / "forecasting"
FIGS = OUT / "figures"
LOCK = OUT / "lstm_exp_lock.json"
PRED = OUT / "lstm_exp_predictions.parquet"
PROD_LOCK = OUT / "model_lock.json"
PROD_PRED = OUT / "predictions_locked.parquet"


def _savefig(fig, name: str) -> str:
    FIGS.mkdir(parents=True, exist_ok=True)
    path = FIGS / name
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return str(path.relative_to(ROOT)).replace("\\", "/")


def _plot_station_mae(by_station: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(9, 4.5))
    s = by_station.sort_values("mae")
    ax.barh(s["station_name"], s["mae"], color="#4C78A8", label="LSTM exp")
    ax.plot(s["mae_persistence"], s["station_name"], "o", color="#F58518", label="Persistence")
    ax.set_xlabel("Test MAE (µg/m³)")
    ax.set_title("Test MAE by station (LSTM vs persistence)")
    ax.legend(loc="lower right")
    return _savefig(fig, "error_lstm_exp_mae_by_station.png")


def _plot_hour_mae(by_hour: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(8, 3.5))
    h = by_hour.sort_values("hour")
    ax.plot(h["hour"], h["mae"], marker="o", label="LSTM exp")
    ax.plot(h["hour"], h["mae_persistence"], marker="o", label="Persistence")
    ax.set_xlabel("Hour of day")
    ax.set_ylabel("Test MAE")
    ax.set_title("Test MAE by hour (LSTM exp)")
    ax.set_xticks(range(0, 24, 2))
    ax.legend()
    return _savefig(fig, "error_lstm_exp_mae_by_hour.png")


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
    ax.set_title("Test LSTM: actual vs predicted (sample)")
    return _savefig(fig, "error_lstm_exp_actual_vs_pred.png")


def _plot_residual_by_bin(bins: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(8, 3.8))
    ax.bar(range(len(bins)), bins["mae"], color="#54A24B")
    ax.set_xticks(range(len(bins)))
    ax.set_xticklabels(bins["actual_bin"], rotation=30, ha="right")
    ax.set_ylabel("MAE")
    ax.set_title("Test MAE by actual PM2.5 bin (LSTM exp)")
    return _savefig(fig, "error_lstm_exp_mae_by_actual_bin.png")


def _v2_winter_and_high_bin() -> tuple[float | None, float | None]:
    """Optional HistGB v2 reference from production predictions."""
    if not PROD_PRED.is_file():
        return None, None
    try:
        v2 = load_predictions_with_names(PROD_PRED)
        tables = build_error_report_tables(v2)
        winter = tables["test_by_season"]
        winter = winter[winter["season"] == "winter"]
        winter_mae = float(winter["mae"].iloc[0]) if len(winter) else None
        bins = tables["test_residual_by_actual_bin"]
        high = bins[bins["actual_bin"].astype(str).str.contains("150|250")]
        high_mae = float(high["mae"].mean()) if len(high) else None
        return winter_mae, high_mae
    except Exception:  # noqa: BLE001
        return None, None


def _recommendation(
    comparison: dict,
    by_season: pd.DataFrame,
    by_bin: pd.DataFrame,
) -> str:
    beats_v2 = comparison.get("beats_histgb_v2_on_test")
    beats_pers = comparison.get("beats_persistence_on_test")
    winter = by_season[by_season["season"] == "winter"]
    winter_mae = float(winter["mae"].iloc[0]) if len(winter) else None
    high_bins = by_bin[by_bin["actual_bin"].astype(str).str.contains("115|150|250")]
    high_mae = float(high_bins["mae"].mean()) if len(high_bins) else None
    v2_winter, v2_high = _v2_winter_and_high_bin()

    winter_note = ""
    if winter_mae is not None and v2_winter is not None:
        winter_note = f" Winter MAE LSTM≈{winter_mae:.2f} vs HistGB v2≈{v2_winter:.2f}."
    high_note = ""
    if high_mae is not None and v2_high is not None:
        high_note = f" High-bin (≥150) MAE LSTM≈{high_mae:.2f} vs v2≈{v2_high:.2f}."

    if beats_v2 and beats_pers:
        return (
            "LSTM thắng persistence và HistGB v2 trên test — "
            "**cân nhắc Promote** (plan riêng; chưa làm trong vòng này)."
            + winter_note
            + high_note
        )
    if beats_pers and beats_v2 is False:
        return (
            "LSTM thắng persistence nhưng **chưa** thắng HistGB v2 trên test — "
            "**giữ production v2**; không Promote."
            + winter_note
            + high_note
        )
    if not beats_pers:
        return (
            "LSTM **không** thắng persistence trên test — giữ HistGB v2; "
            "xem error_lstm_exp_* trước khi thử kiến trúc khác."
            + winter_note
            + high_note
        )
    return (
        "Không đủ số liệu so với HistGB v2 — kiểm tra model_lock.json / lstm_exp_comparison.json."
    )


def write_markdown(
    metrics: dict,
    tables: dict[str, pd.DataFrame],
    figures: dict[str, str],
    comparison: dict,
    recommendation: str,
) -> str:
    by_st = tables["test_by_station"].sort_values("mae")
    best = by_st.iloc[0]
    worst = by_st.iloc[-1]
    by_cl = tables["test_by_cluster"]
    by_season = tables["test_by_season"].sort_values("mae")
    worst_days = tables["test_worst_days"].head(8)
    by_bin = tables["test_residual_by_actual_bin"]

    histgb = comparison.get("histgb_v2_prod_test_mae", float("nan"))
    lines = [
        "# Vòng B – Forecast error analysis LSTM experiment",
        "",
        "**Model:** PyTorch LSTM (seq=24, hidden=64)  ",
        "**Primary test:** 2016-07-01 → 2016-12-31  ",
        f"**Test n (sequences):** {metrics['n_test']:,}",
        "",
        "## So sánh tổng (test)",
        "",
        "| Model | Test MAE |",
        "|-------|----------|",
        f"| Persistence | {metrics['persistence']['mae']:.3f} |",
        f"| HistGB v2 (production) | {histgb:.3f} |",
        f"| **LSTM exp** | **{metrics['locked']['mae']:.3f}** |",
        "",
        f"Lift LSTM vs persistence: **{metrics['mae_lift']:.3f}** µg/m³.  ",
        f"Δ vs HistGB v2 (LSTM − v2): **{comparison.get('delta_vs_histgb_v2_test_mae')}** "
        "(âm = LSTM tốt hơn).",
        "",
        "## Khuyến nghị",
        "",
        recommendation,
        "",
        "## By station (test)",
        "",
        f"- Best MAE: **{best['station_name']}** ({best['mae']:.2f})",
        f"- Worst MAE: **{worst['station_name']}** ({worst['mae']:.2f})",
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
        "## By actual bin (test)",
        "",
        "| bin | n | MAE |",
        "|-----|---|-----|",
    ]
    for _, r in by_bin.iterrows():
        lines.append(f"| {r['actual_bin']} | {int(r['n'])} | {r['mae']:.2f} |")

    lines += [
        "",
        f"![MAE by hour](figures/{Path(figures['hour']).name})",
        "",
        f"![Actual vs pred](figures/{Path(figures['scatter']).name})",
        "",
        f"![MAE by actual bin](figures/{Path(figures['bins']).name})",
        "",
        "### Worst station-days (test)",
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
        "## Artifacts",
        "",
        "- `error_lstm_exp_*.csv`, `lstm_exp_error_analysis.md`",
        "- `lstm_exp_comparison.json`, `lstm_exp_lock.json`",
        "- Production lock **unchanged:** `model_lock.json`",
        "",
    ]
    path = OUT / "lstm_exp_error_analysis.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path.relative_to(ROOT)).replace("\\", "/")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    FIGS.mkdir(parents=True, exist_ok=True)

    try:
        if not LOCK.is_file():
            raise FileNotFoundError("Missing lstm_exp_lock.json — run lstm_b first")
        lock = json.loads(LOCK.read_text(encoding="utf-8"))
        comparison = lock.get("comparison_vs_histgb_v2") or {}
        if not comparison and PROD_LOCK.is_file():
            prod = json.loads(PROD_LOCK.read_text(encoding="utf-8"))
            comparison = {
                "histgb_v2_prod_test_mae": prod.get("test_mae", {}).get(
                    "hist_gradient_boosting"
                ),
                "beats_persistence_on_test": lock.get("beats_persistence_on_test"),
                "beats_histgb_v2_on_test": lock.get("beats_histgb_v2_on_test"),
            }

        df = load_predictions_with_names(PRED)
        tables = build_error_report_tables(df)
        metrics = overall_test_metrics(df)
        test = df[df["split"] == "test"]

        for name, table in tables.items():
            table.to_csv(OUT / f"error_lstm_exp_{name}.csv", index=False)

        figures = {
            "station": _plot_station_mae(tables["test_by_station"]),
            "hour": _plot_hour_mae(tables["test_by_hour"]),
            "scatter": _plot_residual_scatter(test),
            "bins": _plot_residual_by_bin(tables["test_residual_by_actual_bin"]),
        }

        recommendation = _recommendation(
            comparison,
            tables["test_by_season"],
            tables["test_residual_by_actual_bin"],
        )
        md = write_markdown(metrics, tables, figures, comparison, recommendation)

        summary = {
            "ok": True,
            "phase": "VongB_LSTM_C",
            "test_metrics": metrics,
            "comparison_vs_histgb_v2": comparison,
            "recommendation": recommendation,
            "figures": figures,
            "error_analysis_md": md,
            "csv_prefix": "artifacts/forecasting/error_lstm_exp_",
            "production_lock_unchanged": True,
        }
        path = OUT / "lstm_exp_error_analysis_summary.json"
        path.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(json.dumps(summary, ensure_ascii=True))
        return 0
    except Exception as exc:  # noqa: BLE001
        report = {"ok": False, "phase": "VongB_LSTM_C", "error": str(exc)}
        (OUT / "lstm_exp_error_analysis_summary.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(report, ensure_ascii=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
