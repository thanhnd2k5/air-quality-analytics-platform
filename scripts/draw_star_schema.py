#!/usr/bin/env python3
"""Draw the warehouse star schema → artifacts/dwh/figures/star_schema.png (matplotlib only).

Example:
    python scripts/draw_star_schema.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "dwh" / "figures" / "star_schema.png"

FACT = (
    "fact_air_quality_hourly",
    "Độ mịn: 1 trạm × 1 giờ (420 768 dòng)",
    [
        "Khoá (độ mịn): station_key + date_key + time_key",
        "FK  station_key → dim_station",
        "FK  date_key → dim_date",
        "FK  time_key → dim_time",
        "FK  wind_direction_key → dim_wind_direction",
        "event_time_local",
        "pm25 · pm10 · so2 · no2 · co · o3 (µg/m³)",
        "temperature · pressure · dew_point · rain",
        "wind_speed · relative_humidity · cloud_cover",
        "*_source (uci | openmeteo)",
        "has_missing_* · suspect_cap · data_quality_status",
    ],
)

DIMS = {
    "dim_date": (
        "Thời gian — 1 461 ngày",
        ["PK date_key (YYYYMMDD)", "date_day", "month · month_name", "quarter", "year",
         "season (song song)", "day_of_week · iso_week"],
        "ngày → tháng → quý → năm",
        (0.02, 0.56),
    ),
    "dim_time": (
        "Giờ trong ngày — 24 dòng",
        ["PK time_key (0–23)", "hour · hour_label", "day_part"],
        "giờ → buổi",
        (0.02, 0.10),
    ),
    "dim_station": (
        "Địa điểm — 12 trạm",
        ["PK station_key", "station_code · station_name", "district", "latitude · longitude",
         "coordinate_status"],
        "trạm → quận",
        (0.70, 0.56),
    ),
    "dim_wind_direction": (
        "Hướng gió — 16 hướng + UNKNOWN",
        ["PK wind_direction_key", "wind_direction (N…NNW)", "azimuth_deg",
         "wind_quadrant (NE/SE/SW/NW)", "wind_regime (bắc/nam)"],
        "hướng → phần tư → chế độ gió",
        (0.70, 0.10),
    ),
}

W_DIM, W_FACT = 0.28, 0.34
LINE_H = 0.032


def box(ax, x, y, w, title, subtitle, lines, color, hierarchy=None):
    h = 0.09 + LINE_H * len(lines) + (0.04 if hierarchy else 0)
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.006,rounding_size=0.01",
                                fc="white", ec=color, lw=2))
    ax.add_patch(FancyBboxPatch((x, y + h - 0.075), w, 0.075, boxstyle="round,pad=0.006,rounding_size=0.01",
                                fc=color, ec=color, lw=2))
    ax.text(x + 0.012, y + h - 0.032, title, fontsize=11, fontweight="bold", color="white", va="center")
    ax.text(x + 0.012, y + h - 0.062, subtitle, fontsize=8, color="white", va="center")
    for i, line in enumerate(lines):
        ax.text(x + 0.014, y + h - 0.105 - i * LINE_H, line, fontsize=8.5, va="center",
                family="DejaVu Sans Mono" if line.startswith(("PK", "FK")) else "DejaVu Sans")
    if hierarchy:
        ax.text(x + 0.014, y + 0.022, f"Phân cấp: {hierarchy}", fontsize=8.5, style="italic", color=color,
                va="center")
    return (x, y, w, h)


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(14, 8.5))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    fx, fy = 0.5 - W_FACT / 2, 0.24
    fact_rect = box(ax, fx, fy, W_FACT, FACT[0], FACT[1], FACT[2], "#c2410c")

    for name, (subtitle, lines, hierarchy, (x, y)) in DIMS.items():
        r = box(ax, x, y, W_DIM, name, subtitle, lines, "#0f766e", hierarchy)
        left = x < 0.5
        cx = r[0] + (r[2] if left else 0)
        cy = r[1] + r[3] / 2
        tx = fx if left else fx + W_FACT
        ty = fy + fact_rect[3] * (0.72 if y > 0.4 else 0.28)
        ax.plot([cx, tx], [cy, ty], color="#475569", lw=1.4)
        ax.plot([tx], [ty], marker="o", color="#475569", ms=4)
        ax.text(cx + (0.012 if left else -0.012), cy + 0.014, "1", fontsize=9, color="#475569",
                ha="left" if left else "right")
        ax.text(tx + (-0.012 if left else 0.012), ty + 0.014, "N", fontsize=9, color="#475569",
                ha="right" if left else "left")

    ax.text(0.5, 0.97, "Lược đồ hình sao — kho dữ liệu chất lượng không khí Bắc Kinh (schema dwh)",
            ha="center", fontsize=14, fontweight="bold")
    ax.text(0.5, 0.935, "Số khối con T = (4+1)·(2+1)·(2+1)·(3+1) = 180  ·  tính trước: station×day, station×month, "
            "CUBE(year, season, district, day_part, wind_quadrant) = 32 khối con",
            ha="center", fontsize=9.5, color="#334155")
    fig.savefig(OUT, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
