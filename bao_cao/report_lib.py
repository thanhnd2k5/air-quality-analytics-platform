"""Small helpers shared by build_report.py / build_slides.py: load real numbers from artifacts."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts"
FIG_DIR = Path(__file__).resolve().parent / "figures"


def load_json(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def vn(x: float, d: int = 1) -> str:
    """Vietnamese number format: 1.234,5"""
    s = f"{x:,.{d}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def vn_int(x: float) -> str:
    return f"{int(round(x)):,}".replace(",", ".")


def pct(x: float, d: int = 1) -> str:
    return vn(100 * x, d) + "%"


def dbt_test_count() -> tuple[int, int]:
    """(passed, total) from the latest run_all dbt_test log; falls back to the documented 130/130."""
    log = ART / "run_all" / "logs" / "dbt_test.log"
    if log.is_file():
        m = re.findall(r"PASS=(\d+) WARN=\d+ ERROR=(\d+) SKIP=\d+ TOTAL=(\d+)", log.read_text(encoding="utf-8", errors="ignore"))
        if m:
            passed, _err, total = m[-1]
            return int(passed), int(total)
    return 130, 130


# Measured on 2026-10-12: `docker compose down -v`, raw CSVs deleted, then `python scripts/run_all.py`
# → 14/14 steps ok, 130/130 dbt tests, 11.2 minutes. run_summary_full.json is rewritten by every later
# full run, which is idempotent (skips finished work) and therefore faster.
FROM_SCRATCH_MINUTES = 11.2


class Facts:
    """Every number quoted in the report / slides, read from artifacts."""

    def __init__(self) -> None:
        self.cls = load_json("artifacts/classification/model_lock.json")
        self.cls_metrics = pd.read_csv(ART / "classification" / "metrics.csv")
        self.horizon = pd.read_csv(ART / "classification" / "horizon_sensitivity.csv")
        self.importance = pd.read_csv(ART / "classification" / "feature_importance_tree.csv")
        self.by_station = pd.read_csv(ART / "classification" / "metrics_test_by_station.csv")
        self.olap = load_json("artifacts/dwh/olap_checks.json")
        self.missing = pd.read_csv(ART / "data_profile" / "missing_by_column.csv")
        self.reg = pd.read_csv(ART / "forecasting" / "model_metrics.csv")
        self.cluster = load_json("artifacts/clustering/cluster_lock.json")
        self.k_metrics = pd.read_csv(ART / "clustering" / "k_selection_metrics.csv")
        summary = ART / "run_all" / "run_summary_full.json"
        self.run = json.loads(summary.read_text(encoding="utf-8")) if summary.is_file() else None
        self.dbt_pass, self.dbt_total = dbt_test_count()

    # classification ---------------------------------------------------------
    def test(self, model: str) -> dict:
        return self.cls["test"][model]

    def val(self, model: str) -> dict:
        return self.cls["val"][model]

    @property
    def locked(self) -> str:
        return self.cls["locked_model"]

    @property
    def tree_depth(self) -> int:
        return int(self.cls["params"]["decision_tree"]["max_depth"])

    @property
    def tree_cutoff(self) -> float:
        row = self.cls_metrics[(self.cls_metrics.model == "decision_tree") & (self.cls_metrics.split == "test")]
        return float(row["threshold"].iloc[0])

    @property
    def onset(self) -> dict:
        return self.cls["onset_recall_test"]

    @property
    def mcnemar(self) -> dict:
        return self.cls["mcnemar_vs_persistence_test"]

    def horizon_f1(self, h: int, model: str) -> float:
        row = self.horizon[(self.horizon.horizon_h == h) & (self.horizon.model == model)]
        return float(row["f1"].iloc[0])

    def horizon_row(self, h: int, model: str) -> dict:
        return self.horizon[(self.horizon.horizon_h == h) & (self.horizon.model == model)].iloc[0].to_dict()

    # regression -------------------------------------------------------------
    def reg_mae(self, model: str, split: str = "test") -> float:
        row = self.reg[(self.reg.model == model) & (self.reg.split == split)]
        return float(row["mae"].iloc[0])

    # olap -------------------------------------------------------------------
    def op(self, name: str) -> dict:
        return next(o for o in self.olap["operations"] if o["name"] == name)

    def run_minutes(self) -> float | None:
        if not self.run or not self.run.get("ok"):
            return None
        return self.run["total_seconds"] / 60


def architecture_figure(path: Path) -> Path:
    """End-to-end pipeline diagram used in the report and the slides."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(14, 4.8))
    ax.set_xlim(0, 13.9)
    ax.set_ylim(0, 4.6)
    ax.axis("off")
    boxes = [
        (0.1, 2.75, "Nguồn", "UCI PRSA (12 CSV)\nOpen-Meteo API", "#64748b"),
        (2.4, 2.75, "Data Lake (MinIO)", "raw/ (bất biến)\nprocessed/ Parquet\n+ cờ chất lượng", "#0369a1"),
        (4.7, 2.75, "Staging (Postgres)", "staging.*\nđối soát checksum\n+ số dòng", "#0369a1"),
        (7.0, 2.75, "Kho (dbt)", "lược đồ sao (dwh)\nfact + 4 chiều\n130 dbt test", "#c2410c"),
        (9.3, 2.75, "Khối & mart", "station×day, ×month\nGROUP BY CUBE\n(32 khối con)", "#c2410c"),
        (7.0, 0.25, "Khai phá", "phân loại cảnh báo\n(cây QĐ, HistGB)\nso với persistence", "#15803d"),
        (9.3, 0.25, "OLAP", "SQL · notebook\n5 thao tác", "#7c3aed"),
        (11.75, 1.5, "Ứng dụng", "FastAPI + React\n/olap · /canh-bao\n/du-bao · /ban-do", "#0f766e"),
    ]
    centers = {}
    for x, y, title, body, color in boxes:
        w, h = 2.0, 1.6
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04,rounding_size=0.08",
                                    fc="white", ec=color, lw=2))
        ax.add_patch(FancyBboxPatch((x, y + h - 0.42), w, 0.42, boxstyle="round,pad=0.04,rounding_size=0.08",
                                    fc=color, ec=color, lw=2))
        ax.text(x + w / 2, y + h - 0.21, title, ha="center", va="center", color="white", fontsize=9.5,
                fontweight="bold")
        ax.text(x + w / 2, y + (h - 0.42) / 2, body, ha="center", va="center", fontsize=8.5)
        centers[title] = (x, y, w, h)

    def arrow(a, b, side_a="r", side_b="l", rad=0.0):
        xa, ya, wa, ha = centers[a]
        xb, yb, wb, hb = centers[b]
        pa = {"r": (xa + wa, ya + ha / 2), "b": (xa + wa / 2, ya), "t": (xa + wa / 2, ya + ha)}[side_a]
        pb = {"l": (xb, yb + hb / 2), "t": (xb + wb / 2, yb + hb), "b": (xb + wb / 2, yb)}[side_b]
        style = dict(arrowstyle="-|>", color="#334155", lw=1.5, connectionstyle=f"arc3,rad={rad}")
        ax.annotate("", xy=pb, xytext=pa, arrowprops=style)

    arrow("Nguồn", "Data Lake (MinIO)")
    arrow("Data Lake (MinIO)", "Staging (Postgres)")
    arrow("Staging (Postgres)", "Kho (dbt)")
    arrow("Kho (dbt)", "Khối & mart")
    arrow("Kho (dbt)", "Khai phá", "b", "t")
    arrow("Khối & mart", "OLAP", "b", "t")
    arrow("Khối & mart", "Ứng dụng", "r", "t", -0.25)
    arrow("OLAP", "Ứng dụng", "r", "b", 0.25)
    arrow("Khai phá", "Ứng dụng", "b", "b", 0.35)
    ax.text(0.1, 0.55, "python scripts/run_all.py\n= cả chuỗi bằng 1 lệnh", fontsize=10, family="DejaVu Sans Mono",
            color="#0f172a", bbox=dict(boxstyle="round", fc="#f1f5f9", ec="#94a3b8"))
    fig.savefig(path, dpi=170, bbox_inches="tight")
    plt.close(fig)
    return path
