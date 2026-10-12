#!/usr/bin/env python3
"""Vòng A / A1: build feature matrix v2 + QC + dictionary (does not overwrite v1).

Example:
    py -3 scripts/run_forecasting_v2a.py
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

from src.forecasting.constants import FEATURE_COLS_V2, TARGET_COL  # noqa: E402
from src.forecasting.extract import fetch_forecast_base  # noqa: E402
from src.forecasting.features import build_feature_matrix_v2  # noqa: E402
from src.forecasting.qc import qc_feature_matrix  # noqa: E402

OUT = ROOT / "artifacts" / "forecasting"

FEATURE_DICTIONARY_V2 = """# Forecast feature dictionary v2 (Vòng A)

Target: **`y_pm25_tplus1`** = PM2.5 at station hour **t+1**, using only information available at **t**.

Same split / window as Phase 10 lock. This matrix is **experimental** — does not replace v1 production lock.

## Features (v2 = v1 +)

| Feature | Construction | Leakage note |
|---------|----------------|--------------|
| (all v1 features) | see `feature_dictionary.md` | unchanged |
| `pm25_delta_1` | PM2.5(t) − PM2.5(t−1) | past + t only |
| `pm10_ug_m3`, `co_ug_m3`, `no2_ug_m3` | co-pollutant at t | OK at prediction time |
| `*_lag_{1,2,3,6}` | groupby(station).shift(k) | past only |
| `*_missing` | 1 if pollutant null before impute | OK |
| Pollutant NaN fill | **train median only** | no test median leak |
| `hours_into_episode` | consecutive PM2.5≥115 hours ending at t | causal streak |
| `in_episode_flag` | 1 if streak ≥ 3 | no future island length |

## Explicitly not in v2

O3/SO2, cloud_cover, `hours_since_last_episode`, regional K=6, LSTM.

## Baseline

Persistence: `y_hat(t+1) = pm25_ug_m3` at origin t.
"""


def _write_matrix(df, path: Path) -> str:
    try:
        df.to_parquet(path.with_suffix(".parquet"), index=False)
        return str(path.with_suffix(".parquet").relative_to(ROOT)).replace("\\", "/")
    except Exception:  # noqa: BLE001
        csv_path = path.with_suffix(".csv")
        df.to_csv(csv_path, index=False)
        return str(csv_path.relative_to(ROOT)).replace("\\", "/")


def _jsonify(obj):
    if isinstance(obj, dict):
        return {k: _jsonify(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_jsonify(v) for v in obj]
    if hasattr(obj, "item"):
        return obj.item()
    return obj


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "figures").mkdir(parents=True, exist_ok=True)

    try:
        base = fetch_forecast_base()
        matrix, build_meta = build_feature_matrix_v2(base)
        qc = qc_feature_matrix(
            matrix,
            build_meta=build_meta,
            base_for_leakage=base,
            feature_cols=FEATURE_COLS_V2,
            phase="VongA_A1",
            variant="v2",
        )
    except Exception as exc:  # noqa: BLE001
        report = {
            "ok": False,
            "phase": "VongA_A1",
            "error": str(exc),
            "hint": "Start Postgres and ensure dwh + mart.mart_station_cluster exist.",
        }
        path = OUT / "feature_qc_v2.json"
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"output": str(path), **report}, ensure_ascii=False))
        return 1

    matrix_rel = _write_matrix(matrix, OUT / "feature_matrix_v2")
    preview_cols = [
        c
        for c in [
            "station_key",
            "event_time_local",
            "target_time_local",
            "split",
            "pm25_ug_m3",
            TARGET_COL,
            "pm25_delta_1",
            "pm10_ug_m3",
            "in_episode_flag",
            "hours_into_episode",
            *FEATURE_COLS_V2[:8],
        ]
        if c in matrix.columns
    ]
    preview_path = OUT / "feature_matrix_v2_preview.csv"
    matrix.loc[:, preview_cols].head(200).to_csv(preview_path, index=False)

    dict_path = OUT / "feature_dictionary_v2.md"
    dict_path.write_text(FEATURE_DICTIONARY_V2, encoding="utf-8")

    qc_path = OUT / "feature_qc_v2.json"
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
                "n_features": len(FEATURE_COLS_V2),
                "split_counts": qc["split_counts"],
                "issues": qc["issues"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if qc["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
