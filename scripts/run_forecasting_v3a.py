#!/usr/bin/env python3
"""Feature v3 / B1: build matrix with O3/SO2 + cloud_cover (does not overwrite v2).

Example:
    py -3 scripts/run_forecasting_v3a.py
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

from src.forecasting.constants import FEATURE_COLS_V3, TARGET_COL  # noqa: E402
from src.forecasting.extract import fetch_forecast_base  # noqa: E402
from src.forecasting.features import build_feature_matrix_v3  # noqa: E402
from src.forecasting.qc import qc_feature_matrix  # noqa: E402

OUT = ROOT / "artifacts" / "forecasting"

FEATURE_DICTIONARY_V3 = """# Forecast feature dictionary v3 (O3/SO2 + cloud_cover)

Target: **`y_pm25_tplus1`** = PM2.5 at station hour **t+1**, using only information available at **t**.

Same split / window as production lock. This matrix is **experimental** — does not replace v2 production lock.

## Features (v3 = v2 +)

| Feature | Construction | Leakage note |
|---------|----------------|--------------|
| (all v2 features) | see `feature_dictionary_v2.md` | unchanged |
| `o3_ug_m3`, `so2_ug_m3` | co-pollutant at t | OK at prediction time |
| `o3_*` / `so2_*` lags 1,2,3,6 | groupby(station).shift(k) | past only |
| `o3_ug_m3_missing`, `so2_ug_m3_missing` | 1 if null before impute | OK |
| `cloud_cover_pct` | Open-Meteo at t | OK |
| `cloud_cover_pct_lag_1` | station shift 1 | past only |
| `cloud_cover_pct_missing` | 1 if null before impute | OK |
| NaN fill | **train median only** | no test median leak |

## Explicitly not in v3

LSTM, `hours_since_last_episode`, regional K=6, HistGB retune.

## Baseline

Persistence: `y_hat(t+1) = pm25_ug_m3` at origin t. Compare to HistGB v2 production lock.
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
        matrix, build_meta = build_feature_matrix_v3(base)
        qc = qc_feature_matrix(
            matrix,
            build_meta=build_meta,
            base_for_leakage=base,
            feature_cols=FEATURE_COLS_V3,
            phase="FeatureV3_B1",
            variant="v3",
        )
    except Exception as exc:  # noqa: BLE001
        report = {
            "ok": False,
            "phase": "FeatureV3_B1",
            "error": str(exc),
            "hint": "Start Postgres and ensure dwh + mart.mart_station_cluster exist.",
        }
        path = OUT / "feature_qc_v3.json"
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"output": str(path), **report}, ensure_ascii=False))
        return 1

    matrix_rel = _write_matrix(matrix, OUT / "feature_matrix_v3")
    preview_cols = [
        c
        for c in [
            "station_key",
            "event_time_local",
            "target_time_local",
            "split",
            "pm25_ug_m3",
            TARGET_COL,
            "o3_ug_m3",
            "so2_ug_m3",
            "cloud_cover_pct",
            "in_episode_flag",
            *FEATURE_COLS_V3[:8],
        ]
        if c in matrix.columns
    ]
    preview_path = OUT / "feature_matrix_v3_preview.csv"
    matrix.loc[:, preview_cols].head(200).to_csv(preview_path, index=False)

    dict_path = OUT / "feature_dictionary_v3.md"
    dict_path.write_text(FEATURE_DICTIONARY_V3, encoding="utf-8")

    qc_path = OUT / "feature_qc_v3.json"
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
                "n_features": len(FEATURE_COLS_V3),
                "split_counts": qc["split_counts"],
                "issues": qc["issues"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if qc["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
