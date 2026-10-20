#!/usr/bin/env python3
"""POC: evaluate Open-Meteo boundary_layer_height (PBL) vs PM2.5.

Fetches PBL (+ cloud/temp/wind for comparison) from Open-Meteo archive, joins
station-hour PM2.5/weather from DWH fact (preferred) or UCI MinIO Parquet,
then reports Pearson / partial correlations and a keep/skip heuristic.

Example:
    py -3 scripts/poc_openmeteo_pbl.py --station Wanshouxigong --start 2015-01-01 --end 2015-12-31
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path
from typing import Any

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

from src.ingestion.openmeteo_client import (  # noqa: E402
    fetch_historical_weather,
    hourly_to_records,
)
from src.processing.uci_to_processed import build_processed_key  # noqa: E402
from src.reference.stations import get_station  # noqa: E402
from src.utils.minio_client import (  # noqa: E402
    get_bucket,
    get_minio_client,
    get_object_bytes,
    list_object_names,
)

PBL_HOURLY: tuple[str, ...] = (
    "boundary_layer_height",
    "cloud_cover",
    "temperature_2m",
    "wind_speed_10m",
    "dew_point_2m",
)

EPISODE_PM25 = 115.0


def _finite(value: Any) -> float | None:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if np.isnan(f) or np.isinf(f):
        return None
    return f


def _corr(a: pd.Series, b: pd.Series, method: str = "pearson") -> float | None:
    mask = a.notna() & b.notna()
    if int(mask.sum()) < 30:
        return None
    return _finite(a[mask].astype(float).corr(b[mask].astype(float), method=method))


def _partial_corr(y: pd.Series, x: pd.Series, controls: pd.DataFrame) -> dict[str, Any]:
    """Corr of residuals after OLS of y and x on controls (+ intercept)."""
    cols = [c for c in controls.columns if controls[c].notna().any()]
    frame = pd.concat([y.rename("y"), x.rename("x"), controls[cols]], axis=1).dropna()
    n = int(len(frame))
    if n < 50 or not cols:
        return {"n": n, "partial_pearson": None, "controls": cols}
    yv = frame["y"].to_numpy(dtype=float)
    xv = frame["x"].to_numpy(dtype=float)
    cmat = frame[cols].to_numpy(dtype=float)
    design = np.column_stack([np.ones(n), cmat])
    beta_y, *_ = np.linalg.lstsq(design, yv, rcond=None)
    beta_x, *_ = np.linalg.lstsq(design, xv, rcond=None)
    ry = yv - design @ beta_y
    rx = xv - design @ beta_x
    if np.std(ry) < 1e-12 or np.std(rx) < 1e-12:
        return {"n": n, "partial_pearson": None, "controls": cols}
    return {
        "n": n,
        "partial_pearson": _finite(float(np.corrcoef(ry, rx)[0, 1])),
        "controls": cols,
    }


def _var_sanity(series: pd.Series, *, lo: float | None = None, hi: float | None = None) -> dict:
    s = series.dropna().astype(float)
    out: dict[str, Any] = {
        "n": int(len(s)),
        "null_pct": _finite(float(series.isna().mean() * 100)),
        "min": _finite(float(s.min())) if len(s) else None,
        "max": _finite(float(s.max())) if len(s) else None,
        "mean": _finite(float(s.mean())) if len(s) else None,
        "std": _finite(float(s.std())) if len(s) else None,
    }
    if lo is not None and hi is not None and len(s):
        out["in_range"] = bool(s.between(lo, hi).all())
    return out


def _load_fact_from_dwh(station: str, start: str, end: str) -> pd.DataFrame:
    from src.eda.db import read_sql

    sql = """
        select
            f.event_time_local,
            f.pm25_ug_m3,
            f.temperature_c,
            f.wind_speed_m_s,
            f.relative_humidity_pct,
            f.dew_point_c,
            f.cloud_cover_pct
        from dwh.fact_air_quality_hourly f
        join dwh.dim_station s on s.station_key = f.station_key
        where s.station_name = %s
          and f.event_time_local >= %s::timestamp
          and f.event_time_local < (%s::date + interval '1 day')
        order by f.event_time_local
    """
    df = read_sql(sql, (station, start, end))
    if df.empty:
        raise RuntimeError(f"DWH fact returned 0 rows for {station} [{start}, {end}]")
    df["event_time_local"] = pd.to_datetime(df["event_time_local"])
    df.attrs["source"] = "dwh.fact_air_quality_hourly"
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
    df["event_time_local"] = pd.to_datetime(df["event_time_local"])
    df.attrs["source"] = key
    return df


def _derive_rh(temp_c: pd.Series, dew_c: pd.Series) -> pd.Series:
    """Magnus approximation (%), same idea as warehouse RH derive."""
    t = temp_c.astype(float)
    d = dew_c.astype(float)
    a, b = 17.625, 243.04
    gamma_t = (a * t) / (b + t)
    gamma_d = (a * d) / (b + d)
    rh = 100.0 * np.exp(gamma_d - gamma_t)
    return rh.clip(0, 100)


def _load_base(
    *,
    station: str,
    start: str,
    end: str,
    source: str,
    process_date: str | None,
    uci_parquet: Path | None,
) -> pd.DataFrame:
    if source == "dwh":
        return _load_fact_from_dwh(station, start, end)
    if source == "uci":
        if uci_parquet is not None:
            df = pd.read_parquet(uci_parquet)
            df.attrs["source"] = str(uci_parquet)
        else:
            df = _load_uci_from_minio(station, process_date)
        df = df.copy()
        df["event_time_local"] = pd.to_datetime(df["event_time_local"])
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end) + pd.Timedelta(hours=23)
        df = df[(df["event_time_local"] >= start_ts) & (df["event_time_local"] <= end_ts)]
        if "station_name" in df.columns:
            df = df[df["station_name"] == station]
        if "relative_humidity_pct" not in df.columns and {
            "temperature_c",
            "dew_point_c",
        }.issubset(df.columns):
            df["relative_humidity_pct"] = _derive_rh(df["temperature_c"], df["dew_point_c"])
        return df
    raise ValueError(f"Unknown --source {source}")


def _recommend(metrics: dict[str, Any]) -> dict[str, Any]:
    pbl_r = metrics["corr_with_pm25"].get("boundary_layer_height_m", {}).get("pearson")
    cloud_r = metrics["corr_with_pm25"].get("cloud_cover_pct", {}).get("pearson")
    partial = metrics["partial_corr"].get("pbl_vs_pm25_ctrl_hour_temp_wind", {}).get(
        "partial_pearson"
    )
    episode_delta = metrics.get("episode_contrast", {}).get("pbl_mean_inside_minus_outside")

    abs_pbl = abs(pbl_r) if pbl_r is not None else 0.0
    abs_cloud = abs(cloud_r) if cloud_r is not None else 0.0
    abs_partial = abs(partial) if partial is not None else 0.0

    if abs_partial >= 0.08 and abs_pbl >= abs_cloud + 0.05:
        decision = "PROMOTE_CANDIDATE"
        rationale = (
            f"|partial PBL|={abs_partial:.3f} after hour+temp+wind; "
            f"|r_PBL|={abs_pbl:.3f} beats |r_cloud|={abs_cloud:.3f} — worth ablation."
        )
    elif abs_partial >= 0.05 and abs_pbl > abs_cloud:
        decision = "WEAK_OPTIONAL"
        rationale = (
            f"Incremental signal modest (partial={partial}); "
            "optional ablation only if feature budget allows."
        )
    else:
        decision = "SKIP"
        rationale = (
            f"Little unique signal (partial={partial}, r_PBL={pbl_r}, r_cloud={cloud_r}); "
            "do not expand Open-Meteo ingest for PBL yet."
        )

    if episode_delta is not None and episode_delta > 0:
        rationale += (
            f" Note: PBL mean inside episodes is higher by {episode_delta:.1f} m "
            "(opposite of classic shallow-PBL trapping — check seasonality)."
        )
    elif episode_delta is not None:
        rationale += (
            f" Episode contrast OK: PBL inside episodes lower by {-episode_delta:.1f} m."
        )

    return {
        "decision": decision,
        "abs_pearson_pbl": _finite(abs_pbl),
        "abs_pearson_cloud": _finite(abs_cloud),
        "abs_partial_pbl": _finite(abs_partial),
        "rationale": rationale,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="POC: Open-Meteo PBL vs PM2.5")
    parser.add_argument("--station", default="Wanshouxigong")
    parser.add_argument("--start", default="2015-01-01")
    parser.add_argument("--end", default="2015-12-31")
    parser.add_argument(
        "--source",
        choices=("auto", "dwh", "uci"),
        default="auto",
        help="Station-hour base series: DWH fact preferred, else UCI Parquet",
    )
    parser.add_argument("--process-date", default=None)
    parser.add_argument("--uci-parquet", default=None)
    parser.add_argument(
        "--out-dir",
        default="artifacts/openmeteo/poc_pbl",
        help="Directory for raw JSON + report",
    )
    args = parser.parse_args()

    ref = get_station(args.station)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{ref.station_name.lower()}_{args.start}_{args.end}"

    print(f"Fetching Open-Meteo PBL for {ref.station_name} [{args.start} .. {args.end}] ...")
    om_result = fetch_historical_weather(
        station=ref.station_name,
        latitude=ref.latitude,
        longitude=ref.longitude,
        start_date=args.start,
        end_date=args.end,
        hourly=PBL_HOURLY,
    )
    raw_path = out_dir / f"{stem}_pbl.json"
    meta_path = out_dir / f"{stem}_pbl.meta.json"
    raw_path.write_bytes(om_result.raw_bytes)
    meta_path.write_text(
        json.dumps(om_result.meta.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    om = pd.DataFrame(hourly_to_records(om_result.payload))
    if om.empty:
        raise RuntimeError("Open-Meteo returned 0 hourly rows")
    om["event_time_local"] = pd.to_datetime(om["time"])
    om = om.rename(
        columns={
            "boundary_layer_height": "boundary_layer_height_m",
            "cloud_cover": "om_cloud_cover_pct",
            "temperature_2m": "om_temperature_c",
            "wind_speed_10m": "om_wind_speed_m_s",
            "dew_point_2m": "om_dew_point_c",
        }
    )

    source = args.source
    base_err: str | None = None
    if source == "auto":
        try:
            base = _load_base(
                station=args.station,
                start=args.start,
                end=args.end,
                source="dwh",
                process_date=args.process_date,
                uci_parquet=Path(args.uci_parquet) if args.uci_parquet else None,
            )
            source = "dwh"
        except Exception as exc:  # noqa: BLE001 — POC fallback
            base_err = f"dwh failed: {exc}"
            print(f"DWH unavailable ({exc}); falling back to UCI ...")
            base = _load_base(
                station=args.station,
                start=args.start,
                end=args.end,
                source="uci",
                process_date=args.process_date,
                uci_parquet=Path(args.uci_parquet) if args.uci_parquet else None,
            )
            source = "uci"
    else:
        base = _load_base(
            station=args.station,
            start=args.start,
            end=args.end,
            source=source,
            process_date=args.process_date,
            uci_parquet=Path(args.uci_parquet) if args.uci_parquet else None,
        )

    merged = base.merge(om, on="event_time_local", how="inner")
    if merged.empty:
        raise RuntimeError(
            "Join produced 0 rows — check timezone alignment "
            f"(base {base['event_time_local'].min()}..{base['event_time_local'].max()}, "
            f"OM {om['event_time_local'].min()}..{om['event_time_local'].max()})"
        )

    # Prefer warehouse cloud if present; else OM cloud
    if "cloud_cover_pct" not in merged.columns or merged["cloud_cover_pct"].isna().all():
        merged["cloud_cover_pct"] = merged["om_cloud_cover_pct"]

    merged["hour"] = merged["event_time_local"].dt.hour
    merged["month"] = merged["event_time_local"].dt.month

    feature_cols = {
        "boundary_layer_height_m": "boundary_layer_height_m",
        "cloud_cover_pct": "cloud_cover_pct",
        "temperature_c": "temperature_c"
        if "temperature_c" in merged.columns
        else "om_temperature_c",
        "wind_speed_m_s": "wind_speed_m_s"
        if "wind_speed_m_s" in merged.columns
        else "om_wind_speed_m_s",
        "relative_humidity_pct": "relative_humidity_pct"
        if "relative_humidity_pct" in merged.columns
        else None,
        "hour": "hour",
    }

    corr_block: dict[str, Any] = {}
    for label, col in feature_cols.items():
        if col is None or col not in merged.columns:
            continue
        corr_block[label] = {
            "column": col,
            "pearson": _corr(merged[col], merged["pm25_ug_m3"], "pearson"),
            "spearman": _corr(merged[col], merged["pm25_ug_m3"], "spearman"),
            "n": int((merged[col].notna() & merged["pm25_ug_m3"].notna()).sum()),
        }

    temp_col = feature_cols["temperature_c"]
    wind_col = feature_cols["wind_speed_m_s"]
    controls_htw = merged[["hour", temp_col, wind_col]].rename(
        columns={temp_col: "temperature_c", wind_col: "wind_speed_m_s"}
    )
    controls_htw_rh = controls_htw.copy()
    if feature_cols["relative_humidity_pct"] and feature_cols["relative_humidity_pct"] in merged:
        controls_htw_rh["relative_humidity_pct"] = merged[feature_cols["relative_humidity_pct"]]

    partial_block = {
        "pbl_vs_pm25_ctrl_hour_temp_wind": _partial_corr(
            merged["pm25_ug_m3"], merged["boundary_layer_height_m"], controls_htw
        ),
        "cloud_vs_pm25_ctrl_hour_temp_wind": _partial_corr(
            merged["pm25_ug_m3"], merged["cloud_cover_pct"], controls_htw
        ),
        "pbl_vs_pm25_ctrl_hour_temp_wind_rh": _partial_corr(
            merged["pm25_ug_m3"], merged["boundary_layer_height_m"], controls_htw_rh
        ),
    }

    # Same-hour vs lag-1 PBL (forecast-safe proxy)
    merged["pbl_lag1"] = merged["boundary_layer_height_m"].shift(1)
    partial_block["pbl_lag1_vs_pm25_ctrl_hour_temp_wind"] = _partial_corr(
        merged["pm25_ug_m3"], merged["pbl_lag1"], controls_htw
    )

    dirty = merged["pm25_ug_m3"] >= EPISODE_PM25
    pbl_in = merged.loc[dirty, "boundary_layer_height_m"].dropna()
    pbl_out = merged.loc[~dirty, "boundary_layer_height_m"].dropna()
    episode = {
        "threshold_ug_m3": EPISODE_PM25,
        "hours_inside": int(dirty.sum()),
        "hours_outside": int((~dirty).sum()),
        "pbl_mean_inside": _finite(float(pbl_in.mean())) if len(pbl_in) else None,
        "pbl_mean_outside": _finite(float(pbl_out.mean())) if len(pbl_out) else None,
        "pbl_mean_inside_minus_outside": (
            _finite(float(pbl_in.mean() - pbl_out.mean()))
            if len(pbl_in) and len(pbl_out)
            else None
        ),
        "cloud_mean_inside": _finite(
            float(merged.loc[dirty, "cloud_cover_pct"].mean())
        )
        if dirty.any()
        else None,
        "cloud_mean_outside": _finite(
            float(merged.loc[~dirty, "cloud_cover_pct"].mean())
        )
        if (~dirty).any()
        else None,
    }

    # Seasonal split: DJF vs JJA pearson
    winter = merged["month"].isin([12, 1, 2])
    summer = merged["month"].isin([6, 7, 8])
    seasonal = {
        "winter_djf_pearson_pbl": _corr(
            merged.loc[winter, "boundary_layer_height_m"],
            merged.loc[winter, "pm25_ug_m3"],
        ),
        "summer_jja_pearson_pbl": _corr(
            merged.loc[summer, "boundary_layer_height_m"],
            merged.loc[summer, "pm25_ug_m3"],
        ),
        "winter_djf_pearson_cloud": _corr(
            merged.loc[winter, "cloud_cover_pct"],
            merged.loc[winter, "pm25_ug_m3"],
        ),
        "summer_jja_pearson_cloud": _corr(
            merged.loc[summer, "cloud_cover_pct"],
            merged.loc[summer, "pm25_ug_m3"],
        ),
    }

    metrics = {
        "corr_with_pm25": corr_block,
        "partial_corr": partial_block,
        "episode_contrast": episode,
        "seasonal": seasonal,
    }
    recommendation = _recommend(metrics)

    report = {
        "station": ref.station_name,
        "start": args.start,
        "end": args.end,
        "base_source": source,
        "base_source_detail": base.attrs.get("source"),
        "base_fallback_error": base_err,
        "om_raw_path": str(raw_path).replace("\\", "/"),
        "om_meta_path": str(meta_path).replace("\\", "/"),
        "om_request_url": om_result.meta.request_url,
        "join": {
            "base_rows": int(len(base)),
            "om_rows": int(len(om)),
            "joined_rows": int(len(merged)),
            "pm25_non_null": int(merged["pm25_ug_m3"].notna().sum()),
        },
        "sanity": {
            "boundary_layer_height_m": _var_sanity(
                merged["boundary_layer_height_m"], lo=0.0, hi=5000.0
            ),
            "cloud_cover_pct": _var_sanity(merged["cloud_cover_pct"], lo=0.0, hi=100.0),
        },
        "metrics": metrics,
        "recommendation": recommendation,
    }

    report_path = out_dir / f"{stem}_pbl_report.json"
    text = json.dumps(report, indent=2, sort_keys=True, allow_nan=False)
    report_path.write_text(text, encoding="utf-8")
    print(text)
    print(f"\nWrote {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
