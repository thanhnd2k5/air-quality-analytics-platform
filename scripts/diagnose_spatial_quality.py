"""Offline spatial data-quality diagnostic.

Reads the UCI CSVs and the locked feature matrix. Does not open the warehouse,
retrain a model, or rewrite PM2.5. The detection rule lives in
src/forecasting/spatial_quality.py and does not take a date.

The timestamp below is a reconciliation case only. It is applied after the
rule has already been frozen, and it is not passed into the scorer.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.forecasting.spatial_quality import (  # noqa: E402
    attach_suspect_neighbor_influence,
    score_spatial_quality,
)
from src.forecasting.split import assign_split  # noqa: E402

# Reconciliation case. Not an input to the rule.
DIAGNOSTIC_STATION = "Wanshouxigong"
DIAGNOSTIC_TIME = "2016-12-20 15:00:00"
STATIONS = ROOT / "data" / "raw" / "reference" / "stations.csv"
INVENTORY = ROOT / "data" / "raw" / "reference" / "file_inventory.csv"
CLUSTER = ROOT / "data" / "clustering" / "station_cluster_assignment.csv"
MATRIX = ROOT / "artifacts" / "forecasting" / "feature_matrix_v2.parquet"
OUT = ROOT / "artifacts" / "forecasting" / "spatial_quality"
STABILITY_CONTEXT = (35.0, 50.0, 75.0)
STABILITY_ISOLATION = (0.4, 0.5, 0.6)


def _load_uci() -> pd.DataFrame:
    inventory = pd.read_csv(INVENTORY)
    frames = []
    for row in inventory.itertuples(index=False):
        path = ROOT / row.relative_path
        raw = pd.read_csv(path)
        raw["event_time_local"] = pd.to_datetime(raw[["year", "month", "day", "hour"]])
        raw = raw.rename(
            columns={
                "No": "source_row_no",
                "PM2.5": "pm25_ug_m3",
                "PM10": "pm10_ug_m3",
                "SO2": "so2_ug_m3",
                "NO2": "no2_ug_m3",
                "CO": "co_ug_m3",
                "station": "station_name",
            }
        )
        keep = [
            "source_row_no",
            "station_name",
            "event_time_local",
            "pm25_ug_m3",
            "pm10_ug_m3",
            "so2_ug_m3",
            "no2_ug_m3",
            "co_ug_m3",
        ]
        part = raw[keep].copy()
        part["source_file_name"] = row.file_name
        part["source_bytes"] = path.stat().st_size
        part["inventory_bytes"] = int(row.file_size_bytes)
        frames.append(part)
    panel = pd.concat(frames, ignore_index=True)
    if panel.duplicated(["station_name", "event_time_local"]).any():
        raise ValueError("UCI panel has duplicate station hours")
    return panel


def _reconcile(panel: pd.DataFrame) -> dict:
    moment = pd.Timestamp(DIAGNOSTIC_TIME)
    row = panel[
        panel["station_name"].eq(DIAGNOSTIC_STATION) & panel["event_time_local"].eq(moment)
    ]
    if row.empty:
        raise ValueError(f"UCI row missing for {DIAGNOSTIC_STATION} {DIAGNOSTIC_TIME}")
    source = row.iloc[0]
    keys = pd.read_csv(CLUSTER)[["station_key", "station_name"]]
    station_key = int(keys.loc[keys["station_name"].eq(DIAGNOSTIC_STATION), "station_key"].iloc[0])
    matrix = pd.read_parquet(
        MATRIX,
        columns=[
            "station_key",
            "event_time_local",
            "pm25_ug_m3",
            "pm10_ug_m3",
            "co_ug_m3",
            "no2_ug_m3",
            "pm10_ug_m3_missing",
            "co_ug_m3_missing",
            "no2_ug_m3_missing",
            "split",
        ],
    )
    matrix["event_time_local"] = pd.to_datetime(matrix["event_time_local"])
    locked = matrix[
        matrix["station_key"].eq(station_key) & matrix["event_time_local"].eq(moment)
    ]
    if locked.empty:
        raise ValueError("Locked feature matrix has no row for the reconciliation hour")
    locked_row = locked.iloc[0]
    compared = panel.merge(keys, on="station_name", how="inner").merge(
        matrix[["station_key", "event_time_local", "pm25_ug_m3"]],
        on=["station_key", "event_time_local"],
        how="inner",
        suffixes=("_uci", "_matrix"),
    )
    both = compared["pm25_ug_m3_uci"].notna() & compared["pm25_ug_m3_matrix"].notna()
    gap = (compared.loc[both, "pm25_ug_m3_uci"] - compared.loc[both, "pm25_ug_m3_matrix"]).abs()
    return {
        "station_name": DIAGNOSTIC_STATION,
        "event_time_local": str(moment),
        "role": "reconciliation_only",
        "source_file_name": str(source["source_file_name"]),
        "source_row_no": int(source["source_row_no"]),
        "source_bytes": int(source["source_bytes"]),
        "inventory_bytes": int(source["inventory_bytes"]),
        "bytes_match_inventory": int(source["source_bytes"]) == int(source["inventory_bytes"]),
        "uci_pm25": float(source["pm25_ug_m3"]),
        "uci_pm10": float(source["pm10_ug_m3"]),
        "uci_co": float(source["co_ug_m3"]),
        "uci_no2": float(source["no2_ug_m3"]),
        "uci_so2": float(source["so2_ug_m3"]),
        "matrix_pm25": float(locked_row["pm25_ug_m3"]),
        "matrix_pm10": float(locked_row["pm10_ug_m3"]),
        "matrix_co": float(locked_row["co_ug_m3"]),
        "matrix_no2": float(locked_row["no2_ug_m3"]),
        "matrix_pm10_missing": int(locked_row["pm10_ug_m3_missing"]),
        "matrix_co_missing": int(locked_row["co_ug_m3_missing"]),
        "matrix_no2_missing": int(locked_row["no2_ug_m3_missing"]),
        "matrix_split": str(locked_row["split"]),
        "pm25_matches_matrix": float(source["pm25_ug_m3"]) == float(locked_row["pm25_ug_m3"]),
        "matrix_overlap_rows": int(both.sum()),
        "matrix_pm25_mismatch_rows": int((gap > 0).sum()),
        "matrix_pm25_max_abs_gap": float(gap.max()) if len(gap) else None,
    }


def _diff_summary(frame: pd.DataFrame, column: str) -> dict:
    values = frame[column].replace([np.inf, -np.inf], np.nan).dropna()
    if values.empty:
        return {"n": 0}
    quantiles = values.quantile([0.01, 0.5, 0.99])
    return {
        "n": int(values.shape[0]),
        "p01": float(quantiles.loc[0.01]),
        "p50": float(quantiles.loc[0.5]),
        "p99": float(quantiles.loc[0.99]),
        "share_abs_gt_10": float((values.abs() > 10).mean()),
        "share_abs_gt_20": float((values.abs() > 20).mean()),
        "share_abs_gt_50": float((values.abs() > 50).mean()),
    }


def _jsonable(value):
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if np.isnan(value):
            return None
        return float(value)
    if isinstance(value, (pd.Timestamp,)):
        return str(value)
    if isinstance(value, float) and np.isnan(value):
        return None
    return value


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    panel = _load_uci()
    reconciliation = _reconcile(panel)
    stations = pd.read_csv(STATIONS)
    scored = score_spatial_quality(panel, stations)
    scored = attach_suspect_neighbor_influence(scored)
    scored["split"] = assign_split(scored["event_time_local"]).fillna("outside")
    # The scorer must not have replaced the source concentration.
    source_pm = panel.set_index(["station_name", "event_time_local"])["pm25_ug_m3"]
    scored_pm = scored.set_index(["station_name", "event_time_local"])["pm25_ug_m3"]
    if not source_pm.sort_index().equals(scored_pm.sort_index()):
        raise ValueError("Scorer changed pm25_ug_m3")

    in_split = scored["split"].isin(["train", "val", "test"])
    flagged = scored[in_split & scored["suspect_spatiotemporal"]].copy()
    causal = scored[in_split & scored["suspect_spatiotemporal_causal"]].copy()

    def _counts(frame: pd.DataFrame) -> dict:
        return {split: int((frame["split"] == split).sum()) for split in ("train", "val", "test")}

    stability = []
    for context_min in STABILITY_CONTEXT:
        for isolation_min in STABILITY_ISOLATION:
            mask = (
                in_split
                & scored["context_ug"].ge(context_min)
                & scored["isolation"].ge(isolation_min)
            )
            chosen = scored[mask]
            train_chosen = chosen[chosen["split"] == "train"]
            stability.append(
                {
                    "context_min_ug": context_min,
                    "isolation_min": isolation_min,
                    "frozen_rule": context_min == 50.0 and isolation_min == 0.5,
                    "counts": _counts(chosen),
                    "train_median_pm25": float(train_chosen["pm25_ug_m3"].median())
                    if len(train_chosen)
                    else None,
                    "train_median_gap_ug": float(
                        (train_chosen["context_ug"] - train_chosen["pm25_ug_m3"]).median()
                    )
                    if len(train_chosen)
                    else None,
                }
            )

    base = scored[in_split & scored["neighbor_n_finite"].ge(2)].copy()
    base["idw_minus_median"] = base["neighbor_idw_mean"] - base["neighbor_median"]
    base["idw_minus_trimmed"] = base["neighbor_idw_mean"] - base["neighbor_trimmed_mean"]
    base["mean_minus_median"] = base["neighbor_mean"] - base["neighbor_median"]
    base["idw_minus_excluding"] = base["neighbor_idw_mean"] - base["neighbor_idw_excluding_suspect"]
    sensitivity = []
    for split in ("train", "val", "test"):
        for label, subset in (
            ("all_hours", base[base["split"] == split]),
            ("neighbor_flagged", base[(base["split"] == split) & (base["neighbor_suspect_count"] > 0)]),
        ):
            sensitivity.append(
                {
                    "split": split,
                    "subset": label,
                    "n_hours": int(len(subset)),
                    "idw_minus_median": _diff_summary(subset, "idw_minus_median"),
                    "idw_minus_trimmed": _diff_summary(subset, "idw_minus_trimmed"),
                    "mean_minus_median": _diff_summary(subset, "mean_minus_median"),
                    "idw_minus_excluding_suspect": _diff_summary(subset, "idw_minus_excluding"),
                }
            )

    moment = pd.Timestamp(DIAGNOSTIC_TIME)
    diagnostic_row = scored[
        scored["station_name"].eq(DIAGNOSTIC_STATION) & scored["event_time_local"].eq(moment)
    ].iloc[0]
    diagnostic_hosts = base[
        base["event_time_local"].eq(moment) & (base["neighbor_suspect_count"] > 0)
    ].copy()

    suspect_cols = [
        "station_name",
        "event_time_local",
        "split",
        "pm25_ug_m3",
        "pm10_ug_m3",
        "co_ug_m3",
        "no2_ug_m3",
        "pm25_lag1h",
        "pm25_lead1h",
        "temporal_floor_ug",
        "spatial_median_ug",
        "context_ug",
        "isolation",
        "suspect_spatiotemporal",
        "suspect_spatiotemporal_causal",
        "pm10_context",
        "co_elevated",
        "source_row_no",
    ]
    flagged.sort_values(["split", "event_time_local", "station_name"]).to_csv(
        OUT / "suspect_rows.csv", index=False, columns=suspect_cols
    )
    host_cols = [
        "station_name",
        "event_time_local",
        "split",
        "pm25_ug_m3",
        "neighbor_1_name",
        "neighbor_1_pm25",
        "neighbor_1_suspect",
        "neighbor_2_name",
        "neighbor_2_pm25",
        "neighbor_2_suspect",
        "neighbor_3_name",
        "neighbor_3_pm25",
        "neighbor_3_suspect",
        "neighbor_idw_mean",
        "neighbor_mean",
        "neighbor_median",
        "neighbor_trimmed_mean",
        "neighbor_idw_excluding_suspect",
        "neighbor_mean_excluding_suspect",
        "neighbor_median_excluding_suspect",
        "neighbor_trimmed_excluding_suspect",
        "neighbor_suspect_count",
    ]
    influenced = base[base["neighbor_suspect_count"] > 0].sort_values(
        ["split", "event_time_local", "station_name"]
    )
    influenced.to_csv(OUT / "aggregator_when_neighbor_flagged.csv", index=False, columns=host_cols)

    report = {
        "rule": {
            "context_min_ug": 50.0,
            "isolation_min": 0.5,
            "min_spatial_neighbors": 2,
            "fit_on": "train",
            "validation_used_to_move_cuts": False,
            "diagnostic_timestamp_used_to_move_cuts": False,
            "pm25_rewritten": False,
        },
        "reconciliation": reconciliation,
        "scored_hours": _counts(scored[in_split]),
        "train_isolation_q999_at_context_50": float(
            scored.loc[
                (scored["split"] == "train") & scored["context_ug"].ge(50),
                "isolation",
            ].quantile(0.999)
        ),
        "flag_counts": _counts(flagged),
        "causal_flag_counts": _counts(causal),
        "flagged_pm10_context": {
            f"{split}|{label}": int(count)
            for (split, label), count in flagged.groupby(["split", "pm10_context"]).size().items()
        },
        "flagged_by_year": {
            f"{int(year)}|{split}": int(count)
            for (year, split), count in flagged.groupby(
                [flagged["event_time_local"].dt.year, "split"]
            )
            .size()
            .items()
        },
        "hours_with_pm25_eq_3": {
            split: int(((scored["split"] == split) & np.isclose(scored["pm25_ug_m3"], 3.0)).sum())
            for split in ("train", "val", "test")
        },
        "flagged_among_pm25_eq_3": {
            split: int(
                (
                    (flagged["split"] == split) & np.isclose(flagged["pm25_ug_m3"], 3.0)
                ).sum()
            )
            for split in ("train", "val", "test")
        },
        "stability": stability,
        "sensitivity": sensitivity,
        "diagnostic_hour": {
            "station_name": DIAGNOSTIC_STATION,
            "event_time_local": str(moment),
            "pm25_ug_m3": float(diagnostic_row["pm25_ug_m3"]),
            "suspect_spatiotemporal": bool(diagnostic_row["suspect_spatiotemporal"]),
            "suspect_spatiotemporal_causal": bool(diagnostic_row["suspect_spatiotemporal_causal"]),
            "context_ug": float(diagnostic_row["context_ug"]),
            "isolation": float(diagnostic_row["isolation"]),
            "pm10_context": str(diagnostic_row["pm10_context"]),
            "co_elevated": bool(diagnostic_row["co_elevated"]),
            "spatial_median_ug": float(diagnostic_row["spatial_median_ug"]),
            "temporal_floor_ug": float(diagnostic_row["temporal_floor_ug"]),
            "hosts": diagnostic_hosts[host_cols].to_dict(orient="records"),
        },
    }
    (OUT / "quality_report.json").write_text(json.dumps(_jsonable(report), indent=2), encoding="utf-8")
    print(json.dumps(_jsonable({
        "reconciliation_pm25": reconciliation["uci_pm25"],
        "matches_matrix": reconciliation["pm25_matches_matrix"],
        "mismatch_rows": reconciliation["matrix_pm25_mismatch_rows"],
        "flag_counts": report["flag_counts"],
        "causal_flag_counts": report["causal_flag_counts"],
        "diagnostic_flagged": report["diagnostic_hour"]["suspect_spatiotemporal"],
        "diagnostic_isolation": report["diagnostic_hour"]["isolation"],
        "hosts": len(report["diagnostic_hour"]["hosts"]),
    }), indent=2))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
