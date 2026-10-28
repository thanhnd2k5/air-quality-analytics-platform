#!/usr/bin/env python3
"""Main mining task: PM2.5 exceedance alert classification (t+1h, ≥ 115 µg/m³).

Reads the Vòng A feature matrix (built from the DWH by run_forecasting_v2a.py),
keeps the locked chronological split, trains baselines + Decision Tree + HistGB,
picks the model / cut-off on val only, and reports confusion matrices on test.

Outputs:
    artifacts/classification/  metrics, confusion matrices, lock, predictions, report, figures
    models/pm25_alert/          model.joblib + metadata.json

Example:
    python scripts/run_classification.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import precision_recall_curve  # noqa: E402
from sklearn.tree import export_text, plot_tree  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.classification.constants import (  # noqa: E402
    ALERT_TARGET_COL,
    ALERT_THRESHOLD,
    FEATURE_COLS,
    HORIZON_HOURS,
    LOCK_METRIC,
    RANDOM_STATE,
    SENSITIVITY_HORIZONS,
    TARGET_PM25_COL,
)
from src.classification.metrics import classification_metrics, mcnemar, onset_recall  # noqa: E402
from src.classification.models import (  # noqa: E402
    choose_lock,
    run_decision_tree,
    run_histgb,
    run_majority,
    run_persistence,
)
from src.classification.target import add_alert_target  # noqa: E402
from src.forecasting.constants import (  # noqa: E402
    ML_START,
    TEST_END,
    TEST_START,
    TRAIN_END,
    VAL_END,
    VAL_START,
)

OUT = ROOT / "artifacts" / "classification"
FIG = OUT / "figures"
MODELS = ROOT / "models" / "pm25_alert"
MATRIX = ROOT / "artifacts" / "forecasting" / "feature_matrix_v2.parquet"

MODEL_LABELS = {
    "majority": "Majority (luôn 'không')",
    "persistence": "Persistence (PM2.5(t) ≥ 115)",
    "decision_tree": "Cây quyết định (entropy)",
    "hist_gradient_boosting": "HistGradientBoosting",
}


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def _metrics_rows(results) -> pd.DataFrame:
    rows = []
    for r in results:
        for split, m in r.metrics.items():
            rows.append({"model": r.name, "split": split, "threshold": r.threshold, **m})
    return pd.DataFrame(rows)


def _plot_confusion(results, df: pd.DataFrame, path: Path) -> None:
    test = (df["split"] == "test").to_numpy()
    fig, axes = plt.subplots(1, len(results), figsize=(4.2 * len(results), 4))
    for ax, r in zip(axes, results):
        m = r.metrics["test"]
        # Positive class first, so TP sits top-left as on the dashboard's /canh-bao page.
        cm = np.array([[m["tp"], m["fn"]], [m["fp"], m["tn"]]])
        ax.imshow(cm, cmap="Blues")
        for i in range(2):
            for j in range(2):
                ax.text(j, i, f"{cm[i, j]:,}", ha="center", va="center",
                        color="white" if cm[i, j] > cm.max() / 2 else "black", fontsize=11)
        ax.set_xticks([0, 1], ["Cảnh báo", "Không"])
        ax.set_yticks([0, 1], ["Cảnh báo", "Không"])
        ax.set_xlabel("Dự đoán")
        ax.set_ylabel("Thực tế")
        ax.set_title(f"{MODEL_LABELS[r.name]}\nF1={m['f1']:.3f}  Recall={m['recall']:.3f}", fontsize=9)
    fig.suptitle(f"Ma trận nhầm lẫn trên tập test (2016 H2, n={int(test.sum()):,})")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _plot_pr(results, df: pd.DataFrame, path: Path) -> None:
    test = (df["split"] == "test").to_numpy()
    y = df.loc[test, ALERT_TARGET_COL].to_numpy()
    fig, ax = plt.subplots(figsize=(6, 5))
    for r in results:
        m = r.metrics["test"]
        if r.proba is not None:
            prec, rec, _ = precision_recall_curve(y, r.proba[test])
            ax.plot(rec, prec, label=f"{MODEL_LABELS[r.name]} (PR-AUC={m['pr_auc']:.3f})")
            ax.scatter([m["recall"]], [m["precision"]], s=40, zorder=3)
        elif r.name == "persistence":
            ax.scatter([m["recall"]], [m["precision"]], marker="x", s=80, color="black",
                       label=f"{MODEL_LABELS[r.name]}", zorder=3)
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_xlim(0.5, 1.0)
    ax.set_ylim(0.5, 1.0)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc="lower left")
    ax.set_title("Precision–Recall trên test (chấm = ngưỡng đã chọn trên val)")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _plot_threshold(locked, path: Path) -> None:
    curve = pd.DataFrame(locked.params["threshold_curve_val"])
    fig, ax = plt.subplots(figsize=(6, 4))
    for col in ("precision", "recall", "f1"):
        ax.plot(curve["threshold"], curve[col], marker="o", label=col)
    ax.axvline(locked.threshold, color="grey", linestyle="--", label=f"chọn {locked.threshold:.2f}")
    ax.set_xlabel("Ngưỡng xác suất cảnh báo")
    ax.set_title(f"Chọn ngưỡng trên tập val — {MODEL_LABELS[locked.name]}")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _plot_tree(tree_result, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(13, 6.5))
    plot_tree(
        tree_result.estimator,
        max_depth=2,
        feature_names=list(FEATURE_COLS),
        class_names=["Không", "Cảnh báo"],
        filled=True,
        impurity=False,
        proportion=True,
        rounded=True,
        fontsize=10,
        ax=ax,
    )
    ax.set_title("Cây quyết định (entropy) — 3 tầng đầu")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _plot_importance(tree_result, path: Path) -> pd.DataFrame:
    imp = (
        pd.DataFrame({"feature": list(FEATURE_COLS), "importance": tree_result.estimator.feature_importances_})
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )
    top = imp.head(12).iloc[::-1]
    fig, ax = plt.subplots(figsize=(6, 4.5))
    ax.barh(top["feature"], top["importance"])
    ax.set_xlabel("Độ quan trọng (giảm entropy)")
    ax.set_title("12 thuộc tính quan trọng nhất — cây quyết định")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return imp


def _horizon_sensitivity(matrix: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for h in SENSITIVITY_HORIZONS:
        dfh = add_alert_target(matrix, horizon=h)
        pers = run_persistence(dfh)
        hgb = run_histgb(dfh)
        for r in (pers, hgb):
            m = r.metrics["test"]
            rows.append({
                "horizon_h": h,
                "model": r.name,
                "threshold": r.threshold,
                "precision": m["precision"],
                "recall": m["recall"],
                "f1": m["f1"],
                "test_rows": m["n"],
            })
    return pd.DataFrame(rows)


def _plot_horizon(sens: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(6, 4))
    for model, sub in sens.groupby("model"):
        ax.plot(sub["horizon_h"], sub["f1"], marker="o", label=MODEL_LABELS[model])
    ax.set_xlabel("Tầm dự báo (giờ)")
    ax.set_ylabel("F1 trên test")
    ax.set_xticks(sorted(sens["horizon_h"].unique()))
    ax.grid(alpha=0.3)
    ax.legend()
    ax.set_title("Lợi thế của mô hình tăng khi cảnh báo sớm hơn")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _report_md(lock: dict, metrics: pd.DataFrame, sens: pd.DataFrame, imp: pd.DataFrame) -> str:
    t = metrics[metrics["split"] == "test"].set_index("model")
    lines = [
        "# Phân loại cảnh báo vượt ngưỡng PM2.5 (bài toán khai phá chính)",
        "",
        "**Câu hỏi nghiệp vụ:** trung tâm quan trắc có nên phát cảnh báo *hạn chế hoạt động ngoài trời* "
        f"cho **giờ tới** tại từng trạm không? Nhãn dương: PM2.5(t+{HORIZON_HOURS}h) ≥ {ALERT_THRESHOLD:g} µg/m³ "
        "(ngưỡng đợt ô nhiễm đã khoá ở Phase 8c).",
        "",
        "**Chia tập (khoá từ đầu, theo thời gian):** train 2013-03 → 2015-12 · val 2016-01 → 2016-06 · "
        "test 2016-07 → 2016-12. Độ sâu cây và ngưỡng xác suất chỉ chọn trên val; test chỉ dùng để báo cáo.",
        "",
        "## Kết quả trên tập test",
        "",
        "| Mô hình | Ngưỡng | TP | FP | FN | TN | Accuracy | Precision | Recall | F1 | ROC-AUC |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for name in ("majority", "persistence", "decision_tree", "hist_gradient_boosting"):
        r = t.loc[name]
        auc = "—" if pd.isna(r["roc_auc"]) else f"{r['roc_auc']:.3f}"
        thr = "—" if pd.isna(r["threshold"]) else f"{r['threshold']:.2f}"
        lines.append(
            f"| {MODEL_LABELS[name]} | {thr} | {int(r['tp']):,} | {int(r['fp']):,} | {int(r['fn']):,} | "
            f"{int(r['tn']):,} | {r['accuracy']:.3f} | {r['precision']:.3f} | {r['recall']:.3f} | "
            f"{r['f1']:.3f} | {auc} |"
        )
    on = lock["onset_recall_test"]
    mc = lock["mcnemar_vs_persistence_test"]
    lines += [
        "",
        f"- **Mô hình khoá:** `{lock['locked_model']}` (F1 val cao nhất), ngưỡng xác suất {lock['probability_cutoff']:.2f}.",
        f"- **Accuracy dễ đánh lừa:** mô hình majority đạt accuracy {t.loc['majority', 'accuracy']:.3f} "
        "nhưng recall = 0 — không phát được cảnh báo nào.",
        f"- **Bắt đầu đợt ô nhiễm (onset):** trong {on['locked']['onsets']:,} giờ đang sạch nhưng giờ sau vượt ngưỡng, "
        f"mô hình phát hiện {on['locked']['detected']:,} ({on['locked']['recall']:.1%}); persistence = 0% theo định nghĩa.",
        f"- **McNemar so với persistence (test):** b={mc['b']:,}, c={mc['c']:,}, p={mc['p_value']:.2e} "
        "→ khác biệt có ý nghĩa thống kê." if mc["p_value"] < 0.05 else
        f"- **McNemar so với persistence (test):** p={mc['p_value']:.3f} → chưa có ý nghĩa thống kê.",
        "",
        "## Độ nhạy theo tầm dự báo (test F1)",
        "",
        "| Tầm (giờ) | Persistence | HistGB | Chênh lệch |",
        "|---|---|---|---|",
    ]
    piv = sens.pivot(index="horizon_h", columns="model", values="f1")
    for h, row in piv.iterrows():
        lines.append(
            f"| {h} | {row['persistence']:.3f} | {row['hist_gradient_boosting']:.3f} | "
            f"{row['hist_gradient_boosting'] - row['persistence']:+.3f} |"
        )
    lines += [
        "",
        "## Thuộc tính quan trọng nhất (cây quyết định)",
        "",
        *[f"{i + 1}. `{r.feature}` — {r.importance:.3f}" for i, r in imp.head(8).iterrows()],
        "",
        "Hình: `figures/confusion_matrices_test.png`, `figures/pr_curve_test.png`, "
        "`figures/threshold_tuning_val.png`, `figures/decision_tree_top.png`, "
        "`figures/feature_importance_tree.png`, `figures/horizon_sensitivity.png`.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    MODELS.mkdir(parents=True, exist_ok=True)

    if not MATRIX.is_file():
        print(json.dumps({"ok": False, "error": f"missing {_rel(MATRIX)} — run scripts/run_forecasting_v2a.py"}))
        return 1
    matrix = pd.read_parquet(MATRIX)
    df = add_alert_target(matrix, horizon=HORIZON_HOURS)

    results = [run_majority(df), run_persistence(df), run_decision_tree(df), run_histgb(df)]
    locked = choose_lock(results)
    by_name = {r.name: r for r in results}
    persistence = by_name["persistence"]
    tree = by_name["decision_tree"]

    metrics = _metrics_rows(results)
    metrics.to_csv(OUT / "metrics.csv", index=False)

    confusion = {
        r.name: {s: {k: r.metrics[s][k] for k in ("tn", "fp", "fn", "tp")} for s in ("val", "test")}
        for r in results
    }
    (OUT / "confusion_matrices.json").write_text(json.dumps(confusion, indent=2) + "\n", encoding="utf-8")

    test = (df["split"] == "test").to_numpy()
    y_test = df.loc[test, ALERT_TARGET_COL].to_numpy()
    pm_test = df.loc[test, "pm25_ug_m3"].to_numpy()
    onset = {
        "locked": onset_recall(pm_test, y_test, locked.pred[test], ALERT_THRESHOLD),
        "persistence": onset_recall(pm_test, y_test, persistence.pred[test], ALERT_THRESHOLD),
        "decision_tree": onset_recall(pm_test, y_test, tree.pred[test], ALERT_THRESHOLD),
    }
    mc = mcnemar(y_test, locked.pred[test], persistence.pred[test])
    # McNemar convention here: b = locked right & persistence wrong.
    mc = {"b_locked_right_persistence_wrong": mc["b"], "c_locked_wrong_persistence_right": mc["c"], **mc}

    pred = df[
        ["station_key", "event_time_local", "target_time_local", "split", "pm25_ug_m3",
         TARGET_PM25_COL, ALERT_TARGET_COL, "cluster_id", "cluster_label", "season", "hour"]
    ].copy()
    pred["pred_locked"] = locked.pred
    pred["proba_locked"] = locked.proba
    pred["pred_persistence"] = persistence.pred
    pred["pred_decision_tree"] = tree.pred
    pred["alert_threshold"] = ALERT_THRESHOLD
    pred["probability_cutoff"] = locked.threshold
    pred.to_parquet(OUT / "predictions.parquet", index=False)

    by_station = []
    for station, sub in pred[pred["split"] == "test"].groupby("station_key"):
        for name, col in (("locked", "pred_locked"), ("persistence", "pred_persistence")):
            m = classification_metrics(sub[ALERT_TARGET_COL], sub[col])
            by_station.append({"station_key": station, "model": name, **m})
    pd.DataFrame(by_station).to_csv(OUT / "metrics_test_by_station.csv", index=False)

    (OUT / "tree_rules.txt").write_text(
        export_text(tree.estimator, feature_names=list(FEATURE_COLS), max_depth=4, decimals=1) + "\n",
        encoding="utf-8",
    )

    _plot_confusion(results, df, FIG / "confusion_matrices_test.png")
    _plot_pr(results, df, FIG / "pr_curve_test.png")
    _plot_threshold(locked, FIG / "threshold_tuning_val.png")
    _plot_tree(tree, FIG / "decision_tree_top.png")
    imp = _plot_importance(tree, FIG / "feature_importance_tree.png")
    imp.to_csv(OUT / "feature_importance_tree.csv", index=False)

    sens = _horizon_sensitivity(matrix)
    sens.to_csv(OUT / "horizon_sensitivity.csv", index=False)
    _plot_horizon(sens, FIG / "horizon_sensitivity.png")

    created_at = datetime.now(timezone.utc).isoformat()
    joblib.dump(
        {
            "estimator": locked.estimator,
            "feature_cols": list(FEATURE_COLS),
            "probability_cutoff": locked.threshold,
            "alert_threshold": ALERT_THRESHOLD,
            "horizon_hours": HORIZON_HOURS,
            "model_name": locked.name,
        },
        MODELS / "model.joblib",
    )
    split = {
        "train": {"start": ML_START, "end": TRAIN_END},
        "val": {"start": VAL_START, "end": VAL_END},
        "test": {"start": TEST_START, "end": TEST_END},
    }
    metadata = {
        "model_name": locked.name,
        "task": "binary classification — PM2.5(t+1h) >= 115 ug/m3",
        "horizon_hours": HORIZON_HOURS,
        "alert_threshold": ALERT_THRESHOLD,
        "probability_cutoff": locked.threshold,
        "feature_cols": list(FEATURE_COLS),
        "split": split,
        "random_state": RANDOM_STATE,
        "metrics": locked.metrics,
        "created_at": created_at,
        "dataset": _rel(MATRIX),
    }
    (MODELS / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    def _clean_params(r):
        return {k: v for k, v in r.params.items() if k != "threshold_curve_val"}

    lock = {
        "ok": True,
        "task": metadata["task"],
        "locked_model": locked.name,
        "lock_rule": f"max val {LOCK_METRIC} among learned models (baselines excluded)",
        "probability_cutoff": locked.threshold,
        "alert_threshold": ALERT_THRESHOLD,
        "horizon_hours": HORIZON_HOURS,
        "split": split,
        "class_balance": {
            s: float(df.loc[df["split"] == s, ALERT_TARGET_COL].mean()) for s in ("train", "val", "test")
        },
        "rows": {s: int((df["split"] == s).sum()) for s in ("train", "val", "test")},
        "val": {r.name: r.metrics["val"] for r in results},
        "test": {r.name: r.metrics["test"] for r in results},
        "beats_persistence_on_test_f1": locked.metrics["test"]["f1"] > persistence.metrics["test"]["f1"],
        "onset_recall_test": onset,
        "mcnemar_vs_persistence_test": mc,
        "params": {r.name: _clean_params(r) for r in results},
        "model_artifact": _rel(MODELS / "model.joblib"),
        "created_at": created_at,
    }
    (OUT / "model_lock.json").write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    (OUT / "classification_report.md").write_text(_report_md(lock, metrics, sens, imp), encoding="utf-8")

    print(json.dumps({
        "ok": True,
        "locked_model": locked.name,
        "probability_cutoff": locked.threshold,
        "test_f1": {r.name: round(r.metrics["test"]["f1"], 4) for r in results},
        "onset_recall_locked": round(onset["locked"]["recall"], 4),
        "mcnemar_p": mc["p_value"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
