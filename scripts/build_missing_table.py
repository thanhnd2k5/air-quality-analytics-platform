#!/usr/bin/env python3
"""Per-column missing-value report (all 12 stations) + how each column is handled.

Input : artifacts/data_profile/missing_summary.csv (Phase 1 profiling of the raw CSVs)
Output: artifacts/data_profile/missing_by_column.csv and missing_by_column.md
When the warehouse is reachable, also counts the nulls left in dwh.fact_air_quality_hourly
after processing (column "Còn thiếu trong fact").

Example:
    python scripts/build_missing_table.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

SRC = ROOT / "artifacts" / "data_profile" / "missing_summary.csv"
OUT_CSV = ROOT / "artifacts" / "data_profile" / "missing_by_column.csv"
OUT_MD = ROOT / "artifacts" / "data_profile" / "missing_by_column.md"

POLLUTANT_RULE = (
    "Giữ NULL, không nội suy; gắn cờ has_missing_pollutant / MISSING_MEASUREMENT. "
    "Khai phá: dòng thiếu PM2.5 tại t hoặc t+1 bị loại khỏi ma trận đặc trưng."
)
CO_POLLUTANT_RULE = (
    "Giữ NULL trong kho. Khai phá: điền median của tập TRAIN + cờ *_missing "
    "(không dùng thông tin val/test)."
)
WEATHER_RULE = (
    "Lấp từ Open-Meteo (ERA5) khi UCI thiếu; cột *_source ghi nguồn. "
    "Khai phá: median TRAIN + cờ *_missing nếu vẫn thiếu."
)

# raw UCI name → (fact column, treatment)
COLUMNS = {
    "PM2.5": ("pm25_ug_m3", POLLUTANT_RULE + " Giá trị trần 999 gắn cờ SUSPECT_CAP."),
    "PM10": ("pm10_ug_m3", CO_POLLUTANT_RULE + " Giá trị trần 999 gắn cờ SUSPECT_CAP."),
    "SO2": ("so2_ug_m3", "Giữ NULL + cờ; không dùng làm đặc trưng khai phá."),
    "NO2": ("no2_ug_m3", CO_POLLUTANT_RULE),
    "CO": ("co_ug_m3", CO_POLLUTANT_RULE + " Giá trị trần 10000 gắn cờ SUSPECT_CAP."),
    "O3": ("o3_ug_m3", "Giữ NULL + cờ; không dùng làm đặc trưng khai phá."),
    "TEMP": ("temperature_c", WEATHER_RULE),
    "PRES": ("pressure_hpa", WEATHER_RULE),
    "DEWP": ("dew_point_c", WEATHER_RULE + " Dùng cùng TEMP để suy ra độ ẩm tương đối (công thức Magnus)."),
    "RAIN": ("rain_mm", WEATHER_RULE),
    "WSPM": ("wind_speed_m_s", WEATHER_RULE),
    "wd": (
        "wind_direction",
        "Lấp từ hướng gió Open-Meteo (độ → 16 hướng, macro compass_16); "
        "nếu vẫn thiếu → khoá UNKNOWN (0) của dim_wind_direction.",
    ),
}


def _remaining_nulls() -> dict[str, int] | None:
    try:
        from src.eda.db import fetch_dicts

        exprs = ", ".join(
            f"count(*) filter (where {col} is null)::bigint as {col}" for col, _ in COLUMNS.values()
        )
        return fetch_dicts(f"select {exprs} from dwh.fact_air_quality_hourly")[0]
    except Exception as exc:  # noqa: BLE001 — DB is optional for this report
        print(f"(warehouse not reachable, skipping post-processing nulls: {exc})", file=sys.stderr)
        return None


def main() -> int:
    raw = pd.read_csv(SRC)
    agg = (
        raw.groupby(["variable", "var_type"], sort=False)
        .agg(
            rows=("total_rows", "sum"),
            missing=("missing_count", "sum"),
            worst_station_pct=("missing_pct", "max"),
            longest_gap_h=("longest_missing_run_hours", "max"),
        )
        .reset_index()
    )
    agg["missing_pct"] = (100 * agg["missing"] / agg["rows"]).round(3)
    agg["fact_column"] = agg["variable"].map(lambda v: COLUMNS[v][0])
    agg["treatment"] = agg["variable"].map(lambda v: COLUMNS[v][1])
    remaining = _remaining_nulls()
    agg["remaining_in_fact"] = agg["fact_column"].map(lambda c: remaining.get(c) if remaining else None)
    agg = agg[
        ["variable", "var_type", "fact_column", "rows", "missing", "missing_pct", "worst_station_pct",
         "longest_gap_h", "remaining_in_fact", "treatment"]
    ]
    agg.to_csv(OUT_CSV, index=False)

    lines = [
        "| Cột (UCI) | Cột trong kho | Thiếu | Tỷ lệ | Trạm tệ nhất | Chuỗi thiếu dài nhất | Còn thiếu trong fact | Cách xử lý |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for r in agg.itertuples():
        rem = "—" if pd.isna(r.remaining_in_fact) else f"{int(r.remaining_in_fact):,}"
        lines.append(
            f"| {r.variable} | `{r.fact_column}` | {r.missing:,} | {r.missing_pct:.2f}% | "
            f"{r.worst_station_pct:.2f}% | {int(r.longest_gap_h)} giờ | {rem} | {r.treatment} |"
        )
    lines.append("")
    lines.append(
        f"Tổng {int(agg['rows'].iloc[0]):,} dòng (12 trạm × 35 064 giờ, 2013-03-01 → 2017-02-28). "
        "Các cột No, year, month, day, hour, station không thiếu; ghép thành event_time_local."
    )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUT_CSV.relative_to(ROOT), OUT_MD.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
