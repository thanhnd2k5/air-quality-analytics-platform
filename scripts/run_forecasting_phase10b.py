#!/usr/bin/env python3
"""Phase 10b: build feature matrix + leakage QC + feature dictionary.

Example:
    py -3 scripts/run_forecasting_phase10b.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from src.forecasting.constants import FEATURE_COLS, TARGET_COL  # noqa: E402
from src.forecasting.extract import fetch_forecast_base  # noqa: E402
from src.forecasting.features import build_feature_matrix  # noqa: E402
from src.forecasting.qc import qc_feature_matrix  # noqa: E402

OUT = ROOT / "artifacts" / "forecasting"

FEATURE_DICTIONARY = """# Phase 10b – Forecast feature dictionary

Target: **`y_pm25_tplus1`** = PM2.5 at station hour **t+1**, using only information available at **t**.

## Split (locked)

| Split | Window |
|-------|--------|
| train | 2013-03-01 → 2015-12-31 |
| val | 2016-01-01 → 2016-06-30 |
| test | 2016-07-01 → 2016-12-31 |

2017 excluded from primary eval.

## Meta (not model inputs as-is)

| Column | Notes |
|--------|-------|
| `station_key` | Also used as a feature (integer id / later one-hot in Linear) |
| `event_time_local` | Prediction origin time t |
| `target_time_local` | t+1 |
| `split` | train / val / test |
| `cluster_label` | Human label; model uses `cluster_id` |
| `pm25_ug_m3` | Observed at t — also a **model feature** + persistence baseline |
| `season` | String; model uses `season_code` |

## Features (v1)

| Feature | Construction | Leakage note |
|---------|----------------|--------------|
| `hour` | `time_key` at t | OK |
| `month`, `day_of_week`, `season_code` | from `dim_date` at t | OK |
| `station_key`, `cluster_id` | station + Phase 9 mart | time-invariant join |
| `pm25_ug_m3` | PM2.5 at t (nowcast input) | OK at prediction time |
| `pm25_lag_k` (k=1,2,3,6,12,24) | `groupby(station).shift(k)` = t−k | past only |
| `pm25_roll_mean_6/24` | rolling mean ending at t | includes t, not t+1 |
| weather at t + `_lag_1` | temp / RH / wind | no weather at t+1 |
| `*_missing` | 1 if weather null before impute | OK |
| Weather NaN fill | **train median only**, applied to all splits | no test median leak |

## Baseline

Persistence: `y_hat(t+1) = pm25_ug_m3` at origin t (not `pm25_lag_1`).

## Dropped rows

- Missing target (`pm25` at t+1 null) — no synthetic ground truth
- Missing `pm25_ug_m3` at t — cannot form persistence / core nowcast feature
- Missing any `pm25_lag_*` / `pm25_roll_mean_*` — need ≥24h history per station

## Out of scope (P10e optional)

Episode flags, multi-horizon, pollutant co-lags beyond weather/PM2.5 v1.
"""


def _write_matrix(df, path: Path) -> str:
    """Prefer parquet; fall back to CSV."""
    try:
        df.to_parquet(path.with_suffix(".parquet"), index=False)
        return str(path.with_suffix(".parquet").relative_to(ROOT)).replace("\\", "/")
    except Exception:  # noqa: BLE001 — engine optional
        csv_path = path.with_suffix(".csv")
        df.to_csv(csv_path, index=False)
        return str(csv_path.relative_to(ROOT)).replace("\\", "/")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "figures").mkdir(parents=True, exist_ok=True)

    try:
        base = fetch_forecast_base()
        matrix, build_meta = build_feature_matrix(base)
        qc = qc_feature_matrix(matrix, build_meta=build_meta, base_for_leakage=base)
    except Exception as exc:  # noqa: BLE001
        report = {
            "ok": False,
            "phase": "P10b",
            "error": str(exc),
            "hint": "Start Postgres and ensure dwh + mart.mart_station_cluster exist.",
        }
        path = OUT / "feature_qc.json"
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"output": str(path), **report}, ensure_ascii=False))
        return 1

    matrix_rel = _write_matrix(matrix, OUT / "feature_matrix")
    # Compact column subset for quick inspection
    preview_cols = [
        c
        for c in [
            "station_key",
            "event_time_local",
            "target_time_local",
            "split",
            "pm25_ug_m3",
            TARGET_COL,
            "pm25_lag_1",
            "cluster_id",
            *FEATURE_COLS[:8],
        ]
        if c in matrix.columns
    ]
    preview_path = OUT / "feature_matrix_preview.csv"
    matrix.loc[:, preview_cols].head(200).to_csv(preview_path, index=False)

    dict_path = OUT / "feature_dictionary.md"
    dict_path.write_text(FEATURE_DICTIONARY, encoding="utf-8")

    # JSON-safe build_meta (numpy types)
    def _jsonify(obj):
        if isinstance(obj, dict):
            return {k: _jsonify(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_jsonify(v) for v in obj]
        if hasattr(obj, "item"):
            return obj.item()
        return obj

    qc_path = OUT / "feature_qc.json"
    payload = {
        **_jsonify(qc),
        "matrix": matrix_rel,
        "preview": str(preview_path.relative_to(ROOT)).replace("\\", "/"),
        "dictionary": str(dict_path.relative_to(ROOT)).replace("\\", "/"),
        "sql": "sql/forecasting/extract_forecast_base.sql",
    }
    qc_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "matrix": matrix_rel,
                "qc": str(qc_path),
                "ok": qc["ok"],
                "rows": qc["row_count"],
                "split_counts": qc["split_counts"],
                "issues": qc["issues"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if qc["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
