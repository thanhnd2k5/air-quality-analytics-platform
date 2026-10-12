#!/usr/bin/env python3
"""Write (and optionally execute) notebooks/olap/olap_demo.ipynb — the live OLAP demo.

The notebook runs the named queries from sql/olap/olap_operations.sql against the
warehouse and shows the five OLAP operations, CUBE / ROLLUP / GROUPING SETS and the
cuboid correctness report.

Examples:
    python scripts/build_olap_notebook.py            # write only
    python scripts/build_olap_notebook.py --execute  # write + run, outputs saved in place
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "notebooks" / "olap" / "olap_demo.ipynb"

SETUP = """\
from pathlib import Path
import sys, json, time
ROOT = Path.cwd()
while not (ROOT / "src").exists() and ROOT != ROOT.parent:
    ROOT = ROOT.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

import matplotlib.pyplot as plt
import pandas as pd
from src.olap.queries import load_queries, run_query

pd.set_option("display.max_columns", 20)
pd.set_option("display.width", 160)
Q = load_queries()

def show(name):
    q = Q[name]
    print(f"[{q.op}] {q.desc}")
    return run_query(name, Q)
"""

CELLS: list[tuple[str, str]] = [
    (
        "markdown",
        "# Trình diễn OLAP trên kho dữ liệu chất lượng không khí Bắc Kinh\n\n"
        "**Kho:** PostgreSQL, lược đồ hình sao `dwh.fact_air_quality_hourly` (độ mịn: 1 trạm × 1 giờ, 420 768 dòng).\n\n"
        "| Chiều | Phân cấp khái niệm | Số mức |\n|---|---|---|\n"
        "| Thời gian (`dim_date`) | ngày → tháng → quý → năm (song song: mùa) | 4 |\n"
        "| Giờ trong ngày (`dim_time`) | giờ → buổi | 2 |\n"
        "| Địa điểm (`dim_station`) | trạm → quận | 2 |\n"
        "| Hướng gió (`dim_wind_direction`) | hướng (16) → phần tư (4) → chế độ gió (2) | 3 |\n\n"
        "Số khối con của khối 4 chiều có phân cấp: **T = (4+1)(2+1)(2+1)(3+1) = 180**.\n\n"
        "| Thao tác | Ý nghĩa |\n|---|---|\n"
        "| Roll-up (cuộn lên) | đi lên một mức trong phân cấp, hoặc bỏ bớt một chiều |\n"
        "| Drill-down (khoan xuống) | đi xuống mức chi tiết hơn, hoặc thêm một chiều |\n"
        "| Slice (cắt lát) | cố định một giá trị trên một chiều → khối con ít chiều hơn |\n"
        "| Dice (cắt khối) | chọn khoảng giá trị trên nhiều chiều → khối con nhỏ hơn |\n"
        "| Pivot (xoay trục) | đổi chiều trên hàng / cột — cùng dữ liệu, khung nhìn khác |\n\n"
        "Toàn bộ câu SQL nằm trong `sql/olap/olap_operations.sql`.",
    ),
    ("code", SETUP),
    ("markdown", "## 1. Roll-up — cuộn lên trên chiều Thời gian (ngày → tháng → năm)"),
    (
        "code",
        "day = show('rollup_day'); month = show('rollup_month'); year = show('rollup_year')\n"
        "fig, axes = plt.subplots(1, 3, figsize=(15, 3.5))\n"
        "axes[0].bar(pd.to_datetime(day['date_day']).dt.day, day['pm25_avg']); axes[0].set_title('Dongsi 12/2015 — theo ngày')\n"
        "axes[1].bar(month['month'], month['pm25_avg']); axes[1].set_title('Dongsi 2015 — theo tháng')\n"
        "axes[2].bar(year['year'].astype(str), year['pm25_avg']); axes[2].set_title('Dongsi — theo năm')\n"
        "for ax in axes: ax.axhline(115, color='red', ls='--', lw=1); ax.set_ylabel('PM2.5 (µg/m³)')\n"
        "plt.tight_layout(); plt.show()\n"
        "year",
    ),
    (
        "markdown",
        "Ngày 01/12/2015 trung bình **>500 µg/m³** (đợt khói mù lịch sử ở Bắc Kinh). Khi cuộn lên mức tháng/năm, "
        "đỉnh này bị \"pha loãng\". Đó là lý do phải giữ độ mịn giờ trong bảng sự kiện. "
        "Lưu ý: năm 2017 chỉ có tháng 1–2 (mùa đông) nên trung bình cao hơn.",
    ),
    ("code", "show('rollup_station_to_district')"),
    ("code", "show('rollup_operator')  # dòng NULL = tổng con của mức cha; grouping_id cho biết mức nào bị gộp"),
    ("markdown", "## 2. Drill-down — khoan xuống: năm → quý → tháng → buổi trong ngày"),
    (
        "code",
        "levels = [show('drilldown_year'), show('drilldown_quarter'), show('drilldown_month'), show('drilldown_daypart')]\n"
        "keys = ['year', 'quarter', 'month', 'day_part']\n"
        "titles = ['Năm', 'Quý (2015)', 'Tháng (Q4/2015)', 'Buổi (12/2015)']\n"
        "fig, axes = plt.subplots(1, 4, figsize=(16, 3.2))\n"
        "for ax, df, k, t in zip(axes, levels, keys, titles):\n"
        "    ax.bar(df[k].astype(str), df['pm25_avg']); ax.set_title(t); ax.axhline(115, color='red', ls='--', lw=1)\n"
        "plt.tight_layout(); plt.show()\n"
        "levels[2]",
    ),
    (
        "markdown",
        "Khoan xuống cho thấy quý 4/2015 là đỉnh, tháng 12 xấu nhất (150 µg/m³), và buổi tối/đêm cao hơn buổi sáng. "
        "Đây là gợi ý trực tiếp cho thời điểm phát cảnh báo.",
    ),
    ("markdown", "## 3. Slice — cắt lát tại quận = 'Dongcheng'"),
    (
        "code",
        "s = show('slice_district')\n"
        "s.pivot(index='year', columns='season', values='pm25_avg')[['spring', 'summer', 'autumn', 'winter']]",
    ),
    ("markdown", "## 4. Dice — mùa ∈ {thu, đông} × gió nam/bắc × quận ∈ {Dongcheng, Xicheng}"),
    (
        "code",
        "dice = pd.concat([show('dice_winter_south_core'), show('dice_compare_north')])\n"
        "dice.pivot_table(index=['district', 'season'], columns='wind_regime', values=['pm25_avg', 'pct_exceed'])",
    ),
    (
        "markdown",
        "Với cùng quận và cùng mùa, **gió nam** (khí từ đồng bằng Hà Bắc) làm PM2.5 mùa đông tăng từ ~85 lên ~133 µg/m³, "
        "và tỷ lệ giờ vượt ngưỡng 115 tăng từ ~28% lên ~43%. Đây là lý do chiều Hướng gió được đưa vào kho.",
    ),
    ("markdown", "## 5. Pivot — xoay trục: trạm × tháng ⇄ tháng × trạm"),
    (
        "code",
        "p = show('pivot_station_month').set_index('station_name')\n"
        "fig, ax = plt.subplots(figsize=(10, 4.5))\n"
        "im = ax.imshow(p.values.astype(float), cmap='YlOrRd', aspect='auto')\n"
        "ax.set_xticks(range(12), [c.upper() for c in p.columns]); ax.set_yticks(range(len(p)), p.index)\n"
        "fig.colorbar(im, label='PM2.5 TB (µg/m³)'); ax.set_title('PM2.5 trung bình 2016: trạm × tháng')\n"
        "plt.tight_layout(); plt.show()\n"
        "p.T.head()  # xoay trục: tháng trên hàng, trạm trên cột",
    ),
    ("code", "show('pivot_season_wind')  # đọc từ khối tính trước mart_olap_cube"),
    ("markdown", "## 6. CUBE, GROUPING SETS và trả lời truy vấn từ khối đã tính trước"),
    ("code", "show('cube_operator')"),
    ("code", "show('grouping_sets')"),
    (
        "code",
        "from src.eda.db import read_sql\n"
        "t0 = time.perf_counter()\n"
        "scan = read_sql(\"select calendar.year, calendar.season, avg(f.pm25_ug_m3) as pm25_avg \"\n"
        "                \"from dwh.fact_air_quality_hourly f join dwh.dim_date calendar on f.date_key = calendar.date_key \"\n"
        "                \"group by 1, 2\")\n"
        "t_fact = time.perf_counter() - t0\n"
        "t0 = time.perf_counter(); cube = show('cube_lookup'); t_cube = time.perf_counter() - t0\n"
        "print(f'Quét fact (420 768 dòng): {t_fact*1000:.0f} ms | đọc khối con (17 ô): {t_cube*1000:.0f} ms')\n"
        "cube.head(8)",
    ),
    ("code", "show('cuboid_inventory')"),
    ("markdown", "## 7. Kiểm chứng tính đúng của các khối đã tính trước"),
    (
        "code",
        "checks = json.loads((ROOT / 'artifacts' / 'dwh' / 'olap_checks.json').read_text(encoding='utf-8'))\n"
        "print(checks['summary'])\n"
        "pd.DataFrame(checks['cuboid_checks'])[['cuboid', 'cells', 'matched', 'pct_correct']]",
    ),
    (
        "markdown",
        "Mọi ô của mọi khối con tính trước (station × day, station × month, 32 khối của `mart_olap_cube`) đều được "
        "tính lại từ bảng sự kiện và so khớp số đếm + tổng PM2.5. Script: `python scripts/run_olap_checks.py`.",
    ),
]


def notebook() -> dict:
    cells = []
    for i, (kind, source) in enumerate(CELLS):
        src = source if source.endswith("\n") else source + "\n"
        lines = src.splitlines(keepends=True)
        cell = {"cell_type": kind, "id": f"olap-{i:02d}", "metadata": {}, "source": lines}
        if kind == "code":
            cell.update({"execution_count": None, "outputs": []})
        cells.append(cell)
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "cells": cells,
    }


def execute(path: Path, timeout: int = 600) -> None:
    """Run the notebook with *this* interpreter (not whatever 'python3' kernel is global)."""
    import nbformat
    from nbclient import NotebookClient

    with tempfile.TemporaryDirectory() as tmp:
        spec_dir = Path(tmp) / "kernels" / "python3"
        spec_dir.mkdir(parents=True)
        (spec_dir / "kernel.json").write_text(
            json.dumps(
                {
                    "argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
                    "display_name": "Python 3 (project)",
                    "language": "python",
                }
            ),
            encoding="utf-8",
        )
        old = os.environ.get("JUPYTER_PATH")
        os.environ["JUPYTER_PATH"] = tmp + (os.pathsep + old if old else "")
        try:
            nb = nbformat.read(path, as_version=4)
            NotebookClient(
                nb, timeout=timeout, kernel_name="python3", resources={"metadata": {"path": str(path.parent)}}
            ).execute()
            nbformat.write(nb, path)
        finally:
            if old is None:
                os.environ.pop("JUPYTER_PATH", None)
            else:
                os.environ["JUPYTER_PATH"] = old


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the OLAP demo notebook")
    parser.add_argument("--execute", action="store_true", help="Run it and save outputs")
    args = parser.parse_args()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(notebook(), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.execute:
        execute(OUT)
    print(json.dumps({"ok": True, "notebook": str(OUT.relative_to(ROOT)), "executed": args.execute}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
