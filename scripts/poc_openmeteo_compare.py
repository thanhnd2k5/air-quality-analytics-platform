#!/usr/bin/env python3
"""Phase 5a: compare UCI processed weather vs Open-Meteo POC JSON for one month.

Reads UCI from MinIO processed Parquet (preferred) or a local Parquet path.
Writes correlation / bias / fill-potential report under artifacts/openmeteo/poc/.

Example:
    python scripts/poc_openmeteo_compare.py \\
      --om-json artifacts/openmeteo/poc/wanshouxigong_2015-01-01_2015-01-31.json \\
      --station Wanshouxigong --start 2015-01-01 --end 2015-01-31
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

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

from src.ingestion.openmeteo_client import hourly_to_records  # noqa: E402
from src.processing.uci_to_processed import build_processed_key  # noqa: E402
from src.utils.minio_client import (  # noqa: E402
    get_bucket,
    get_minio_client,
    get_object_bytes,
    list_object_names,
)

# UCI canonical ↔ Open-Meteo hourly field
COMPARE_PAIRS: tuple[tuple[str, str, str], ...] = (
    ("temperature_c", "temperature_2m", "TEMP"),
    ("dew_point_c", "dew_point_2m", "DEWP"),
    ("rain_mm", "rain", "RAIN"),
    ("wind_speed_m_s", "wind_speed_10m", "WSPM"),
    ("pressure_hpa", "surface_pressure", "PRES"),
)


def _load_om_frame(om_json: Path) -> pd.DataFrame:
    payload = json.loads(om_json.read_text(encoding="utf-8"))
    rows = hourly_to_records(payload)
    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError(f"No hourly rows in {om_json}")
    # Open-Meteo with timezone=Asia/Shanghai returns local wall times without offset
    df["event_time_local"] = pd.to_datetime(df["time"])
    return df


def _load_uci_from_minio(station: str, process_date: str | None) -> pd.DataFrame:
    client = get_minio_client()
    bucket = get_bucket()
    if process_date:
        key = build_processed_key(station, process_date)
    else:
        prefix = f"processed/uci/air_quality/station={station}/"
        names = [
            n
            for n in list_object_names(client, bucket, prefix=prefix)
            if n.endswith(".parquet") and "quarantine" not in n
        ]
        if not names:
            raise FileNotFoundError(f"No processed Parquet under {prefix}")
        key = sorted(names)[-1]
    raw = get_object_bytes(client, bucket, key)
    df = pd.read_parquet(io.BytesIO(raw))
    df.attrs["source_object_key"] = key
    return df


def _load_uci(station: str, process_date: str | None, local_parquet: Path | None) -> pd.DataFrame:
    if local_parquet is not None:
        df = pd.read_parquet(local_parquet)
        df.attrs["source_object_key"] = str(local_parquet)
        return df
    return _load_uci_from_minio(station, process_date)


def _finite_or_none(value) -> float | None:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if np.isnan(f) or np.isinf(f):
        return None
    return f


def _pair_metrics(uci: pd.Series, om: pd.Series) -> dict:
    mask = uci.notna() & om.notna()
    n = int(mask.sum())
    if n < 2:
        return {
            "n_paired": n,
            "pearson": None,
            "spearman": None,
            "mae": None,
            "bias_om_minus_uci": None,
        }
    u = uci[mask].astype(float)
    o = om[mask].astype(float)
    return {
        "n_paired": n,
        "pearson": _finite_or_none(u.corr(o, method="pearson")),
        "spearman": _finite_or_none(u.corr(o, method="spearman")),
        "mae": _finite_or_none(np.mean(np.abs(o - u))),
        "bias_om_minus_uci": _finite_or_none(np.mean(o - u)),
    }


def _fill_potential(uci: pd.Series, om: pd.Series) -> dict:
    uci_missing = uci.isna()
    n_missing = int(uci_missing.sum())
    fillable = int((uci_missing & om.notna()).sum())
    return {
        "uci_missing_count": n_missing,
        "uci_missing_pct": float(n_missing / len(uci) * 100) if len(uci) else 0.0,
        "fillable_by_om_count": fillable,
        "fillable_of_missing_pct": float(fillable / n_missing * 100) if n_missing else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="POC: compare UCI vs Open-Meteo")
    parser.add_argument("--station", default="Wanshouxigong")
    parser.add_argument("--start", default="2015-01-01")
    parser.add_argument("--end", default="2015-01-31")
    parser.add_argument(
        "--om-json",
        required=True,
        help="Path to Open-Meteo raw JSON from poc_openmeteo_fetch.py",
    )
    parser.add_argument("--process-date", default=None, help="UCI processed process_date")
    parser.add_argument("--uci-parquet", default=None, help="Local UCI processed Parquet override")
    parser.add_argument(
        "--out",
        default="artifacts/openmeteo/poc/compare_report.json",
        help="Output report path",
    )
    args = parser.parse_args()

    om_path = Path(args.om_json)
    om = _load_om_frame(om_path)
    local = Path(args.uci_parquet) if args.uci_parquet else None
    uci = _load_uci(args.station, args.process_date, local)

    start = pd.Timestamp(args.start)
    end = pd.Timestamp(args.end) + pd.Timedelta(hours=23)
    uci = uci.copy()
    uci["event_time_local"] = pd.to_datetime(uci["event_time_local"])
    uci = uci[(uci["event_time_local"] >= start) & (uci["event_time_local"] <= end)]
    if "station_name" in uci.columns:
        uci = uci[uci["station_name"] == args.station]

    merged = uci.merge(om, on="event_time_local", how="inner", suffixes=("_uci", "_om"))
    if merged.empty:
        raise RuntimeError(
            "Join produced 0 rows — check timezone alignment "
            f"(UCI range {uci['event_time_local'].min()}..{uci['event_time_local'].max()}, "
            f"OM {om['event_time_local'].min()}..{om['event_time_local'].max()})"
        )

    comparisons = {}
    fill = {}
    for uci_col, om_col, label in COMPARE_PAIRS:
        if uci_col not in merged.columns or om_col not in merged.columns:
            comparisons[label] = {"error": f"missing columns {uci_col}/{om_col}"}
            continue
        comparisons[label] = {
            "uci_column": uci_col,
            "om_column": om_col,
            **_pair_metrics(merged[uci_col], merged[om_col]),
        }
        fill[label] = {
            "uci_column": uci_col,
            "om_column": om_col,
            **_fill_potential(merged[uci_col], merged[om_col]),
        }

    cloud = None
    if "cloud_cover" in merged.columns:
        cc = merged["cloud_cover"].dropna().astype(float)
        cloud = {
            "n": int(len(cc)),
            "min": float(cc.min()) if len(cc) else None,
            "max": float(cc.max()) if len(cc) else None,
            "mean": float(cc.mean()) if len(cc) else None,
            "in_0_100": bool(cc.between(0, 100).all()) if len(cc) else None,
            "null_pct": float(merged["cloud_cover"].isna().mean() * 100),
        }

    report = {
        "station": args.station,
        "start": args.start,
        "end": args.end,
        "uci_source": uci.attrs.get("source_object_key"),
        "om_json": str(om_path).replace("\\", "/"),
        "join": {
            "uci_rows_in_window": int(len(uci)),
            "om_rows": int(len(om)),
            "joined_rows": int(len(merged)),
            "join_key": ["station_name", "event_time_local"],
        },
        "comparisons": comparisons,
        "fill_potential": fill,
        "cloud_cover_sanity": cloud,
        "gate_b_recommendation": _recommend_gate(comparisons, fill, cloud),
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report, indent=2, sort_keys=True, allow_nan=False)
    out_path.write_text(text, encoding="utf-8")
    print(text)
    return 0


def _recommend_gate(comparisons: dict, fill: dict, cloud: dict | None) -> dict:
    """Heuristic Gate B suggestion (human still records final decision)."""
    pears = [
        comparisons[k]["pearson"]
        for k in ("TEMP", "DEWP", "WSPM")
        if isinstance(comparisons.get(k), dict)
        and _finite_or_none(comparisons[k].get("pearson")) is not None
    ]
    mean_r = float(np.mean(pears)) if pears else None
    fillable = [
        fill[k]["fillable_by_om_count"]
        for k in fill
        if isinstance(fill.get(k), dict) and fill[k].get("fillable_by_om_count") is not None
    ]
    cloud_ok = bool(cloud and cloud.get("in_0_100") and (cloud.get("n") or 0) > 0)

    # Prefer B when alignment is reasonable OR enrichment/fill has value
    if mean_r is not None and mean_r >= 0.5 and cloud_ok:
        choice = "B"
        rationale = (
            f"Mean Pearson(TEMP/DEWP/WSPM)={mean_r:.3f}; cloud_cover present & in 0–100; "
            "prefer enrichment + UCI-primary fill (working preference)."
        )
    elif cloud_ok or (fillable and sum(fillable) > 0):
        choice = "B"
        rationale = (
            "Enrichment and/or fill potential still useful despite moderate correlation; "
            "recommend B (enrichment + fill), not full replacement."
        )
    else:
        choice = "C"
        rationale = "Weak alignment and little fill/enrichment signal — consider reducing role."

    return {
        "suggested": choice,
        "mean_pearson_temp_dewp_wspm": mean_r,
        "cloud_cover_ok": cloud_ok,
        "rationale": rationale,
        "note": "Final Gate B must be recorded in PROJECT_CONTEXT.md / PROGRESS.md",
    }


if __name__ == "__main__":
    raise SystemExit(main())
