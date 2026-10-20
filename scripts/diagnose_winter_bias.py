#!/usr/bin/env python3
"""Winter signed-error diagnosis on the locked HistGB v2 predictions.

Does not retrain and does not touch the model lock. High-PM and episode
labels are applied after the forecast, from actual PM2.5 only.

Example:
    py -3 scripts/diagnose_winter_bias.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.forecasting.constants import EPISODE_MIN_HOURS, EPISODE_THRESHOLD, TARGET_COL  # noqa: E402
from src.forecasting.spatial_calendar import (  # noqa: E402
    add_calendar_features,
    add_spatial_features,
    statutory_heating_mask,
)

OUT = ROOT / "artifacts" / "forecasting" / "winter_bias"
PRED_CANDIDATES = (
    ROOT / "artifacts" / "forecasting" / "predictions_locked.parquet",
    ROOT / "artifacts" / "forecasting" / "predictions_v2.parquet",
)
STATION_MAP = ROOT / "data" / "clustering" / "station_cluster_assignment.csv"
STATIONS = ROOT / "data" / "raw" / "reference" / "stations.csv"

ACTUAL_BINS = [0, 35, 75, 115, 150, 250, 500, 1000]
DELTA_BINS = [-1000, -40, -20, -5, 5, 20, 40, 1000]
RAPID_RISE = 20.0
NEIGHBOR_LEAD = 10.0


def _load_predictions() -> tuple[pd.DataFrame, str]:
    for path in PRED_CANDIDATES:
        if path.is_file():
            df = pd.read_parquet(path)
            df["event_time_local"] = pd.to_datetime(df["event_time_local"])
            df["target_time_local"] = pd.to_datetime(df["target_time_local"])
            return df, str(path.relative_to(ROOT)).replace("\\", "/")
    raise FileNotFoundError("No locked or v2 predictions parquet found")


def _attach_names(df: pd.DataFrame) -> pd.DataFrame:
    stations = pd.read_csv(STATION_MAP)[["station_key", "station_name", "district"]]
    out = df.merge(stations, on="station_key", how="left")
    if out["station_name"].isna().any():
        missing = out.loc[out["station_name"].isna(), "station_key"].unique().tolist()
        raise KeyError(f"station_key missing from cluster map: {missing}")
    return out


def _slice_summary(sub: pd.DataFrame) -> dict[str, float | int | None]:
    if sub.empty:
        return {"n": 0, "mae": None, "mean_signed_error": None, "median_signed_error": None,
                "mean_actual": None, "mean_pred": None, "persistence_mae": None,
                "persistence_mean_signed_error": None, "mean_actual_delta": None,
                "mean_pred_delta": None, "response_ratio": None}
    actual_delta = sub["actual_delta"]
    pred_delta = sub["pred_delta"]
    ratio = None
    if float(actual_delta.mean()) != 0:
        ratio = float(pred_delta.mean() / actual_delta.mean())
    return {
        "n": int(len(sub)),
        "mae": float(sub["abs_error"].mean()),
        "mean_signed_error": float(sub["signed_error"].mean()),
        "median_signed_error": float(sub["signed_error"].median()),
        "mean_actual": float(sub[TARGET_COL].mean()),
        "mean_pred": float(sub["y_hat_locked"].mean()),
        "persistence_mae": float((sub[TARGET_COL] - sub["y_hat_persistence"]).abs().mean()),
        "persistence_mean_signed_error": float((sub["y_hat_persistence"] - sub[TARGET_COL]).mean()),
        "mean_actual_delta": float(actual_delta.mean()),
        "mean_pred_delta": float(pred_delta.mean()),
        "response_ratio": ratio,
    }


def _binned(sub: pd.DataFrame, col: str, bins: list[float]) -> list[dict[str, object]]:
    if sub.empty:
        return []
    labels = pd.cut(sub[col], bins=bins, right=False)
    rows = []
    for key, part in sub.groupby(labels, observed=False):
        if part.empty:
            continue
        rows.append(
            {
                "bin": str(key),
                "n": int(len(part)),
                "mae": float(part["abs_error"].mean()),
                "mean_signed_error": float(part["signed_error"].mean()),
                "mean_actual": float(part[TARGET_COL].mean()),
                "mean_pred": float(part["y_hat_locked"].mean()),
                "mean_actual_delta": float(part["actual_delta"].mean()),
                "mean_pred_delta": float(part["pred_delta"].mean()),
            }
        )
    return rows


def _mark_episodes(df: pd.DataFrame) -> pd.DataFrame:
    """Post-hoc episodes on actual target PM2.5. Not used as a model feature."""
    out = df.sort_values(["station_key", "target_time_local"]).reset_index(drop=True)
    episode_id = np.full(len(out), -1, dtype=int)
    phase = np.array([""] * len(out), dtype=object)
    next_id = 0
    for _, idx in out.groupby("station_key", sort=False).groups.items():
        idx = np.asarray(idx)
        block = out.loc[idx]
        y = block[TARGET_COL].to_numpy(dtype=float)
        times = block["target_time_local"].to_numpy()
        dirty = np.isfinite(y) & (y >= EPISODE_THRESHOLD)
        start = 0
        while start < len(block):
            if not dirty[start]:
                start += 1
                continue
            end = start
            while end + 1 < len(block) and dirty[end + 1]:
                gap = times[end + 1] - times[end]
                if gap != np.timedelta64(1, "h"):
                    break
                end += 1
            length = end - start + 1
            if length >= EPISODE_MIN_HOURS:
                sl = idx[start : end + 1]
                episode_id[sl] = next_id
                y_ep = y[start : end + 1]
                peak_local = int(np.nanargmax(y_ep))
                for offset, row_i in enumerate(sl):
                    tags = []
                    if offset < 3:
                        tags.append("onset")
                    if offset == peak_local:
                        tags.append("peak")
                    delta = out.at[row_i, "actual_delta"]
                    if np.isfinite(delta) and delta >= RAPID_RISE:
                        tags.append("rising")
                    elif np.isfinite(delta) and delta <= -RAPID_RISE:
                        tags.append("falling")
                    phase[row_i] = "+".join(tags) if tags else "body"
                next_id += 1
            start = end + 1
    out["episode_id"] = episode_id
    out["episode_phase"] = phase
    return out


def _phase_table(sub: pd.DataFrame) -> list[dict[str, object]]:
    rows = []
    tagged = sub[sub["episode_id"] >= 0]
    if tagged.empty:
        return rows
    for phase_name in ("onset", "rising", "peak", "falling", "body"):
        if phase_name == "body":
            part = tagged[tagged["episode_phase"].eq("body")]
        else:
            part = tagged[tagged["episode_phase"].str.contains(phase_name, regex=False)]
        if part.empty:
            continue
        summary = _slice_summary(part)
        summary["phase"] = phase_name
        summary["n_episodes"] = int(part["episode_id"].nunique())
        rows.append(summary)
    return rows


def _neighbor_lead(sub: pd.DataFrame) -> dict[str, object]:
    rapid = sub[sub["actual_delta"] >= RAPID_RISE].copy()
    if rapid.empty:
        return {"n_rapid": 0}
    gradient = rapid["spatial_gradient"]
    neighbors_higher = rapid["neighbor_pm25_mean"] >= (rapid["pm25_ug_m3"] + NEIGHBOR_LEAD)
    neighbors_lower = rapid["neighbor_pm25_mean"] <= (rapid["pm25_ug_m3"] - NEIGHBOR_LEAD)
    finite = gradient.notna()
    corr = None
    if int(finite.sum()) >= 3:
        corr = float(np.corrcoef(gradient[finite], rapid.loc[finite, "signed_error"])[0, 1])

    def _mean_signed(mask: pd.Series) -> float | None:
        part = rapid[mask]
        if part.empty:
            return None
        return float(part["signed_error"].mean())

    return {
        "n_rapid": int(len(rapid)),
        "mean_signed_error": float(rapid["signed_error"].mean()),
        "mean_actual_delta": float(rapid["actual_delta"].mean()),
        "mean_pred_delta": float(rapid["pred_delta"].mean()),
        "response_ratio": float(rapid["pred_delta"].mean() / rapid["actual_delta"].mean()),
        "frac_neighbors_higher_by_10": float(neighbors_higher.mean()),
        "frac_neighbors_lower_by_10": float(neighbors_lower.mean()),
        "mean_signed_when_neighbors_higher": _mean_signed(neighbors_higher),
        "mean_signed_when_neighbors_lower": _mean_signed(neighbors_lower),
        "mean_signed_when_gradient_near_zero": _mean_signed(~neighbors_higher & ~neighbors_lower),
        "corr_gradient_vs_signed_error": corr,
        "mean_spatial_gradient": float(gradient.mean()),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    raw, pred_path = _load_predictions()
    df = _attach_names(raw)
    stations = pd.read_csv(STATIONS)
    df, neighbor_table = add_spatial_features(df, stations)
    df = add_calendar_features(df)
    df["signed_error"] = df["y_hat_locked"] - df[TARGET_COL]
    df["abs_error"] = df["signed_error"].abs()
    df["actual_delta"] = df[TARGET_COL] - df["pm25_ug_m3"]
    df["pred_delta"] = df["y_hat_locked"] - df["pm25_ug_m3"]
    df["winter"] = df["season"].astype(str).str.lower().eq("winter")
    df["heating_statutory"] = statutory_heating_mask(df["event_time_local"])
    df = _mark_episodes(df)

    scopes = {
        "test": df["split"].eq("test"),
        "test_winter": df["split"].eq("test") & df["winter"],
        "test_heating_statutory": df["split"].eq("test") & df["heating_statutory"],
        "val_winter": df["split"].eq("val") & df["winter"],
        "val_heating_statutory": df["split"].eq("val") & df["heating_statutory"],
        "test_december": df["split"].eq("test") & (df["event_time_local"].dt.month == 12),
    }

    summaries = {name: _slice_summary(df[mask]) for name, mask in scopes.items()}
    winter_test = df[scopes["test_winter"]]
    bins_actual = _binned(winter_test, TARGET_COL, ACTUAL_BINS)
    bins_delta = _binned(winter_test, "actual_delta", DELTA_BINS)
    phases = {
        "test_winter": _phase_table(df[scopes["test_winter"]]),
        "val_winter": _phase_table(df[scopes["val_winter"]]),
    }
    lead = {
        "test_winter": _neighbor_lead(df[scopes["test_winter"]]),
        "val_winter": _neighbor_lead(df[scopes["val_winter"]]),
        "test_all": _neighbor_lead(df[scopes["test"]]),
    }

    # CNY is outside the test window (test starts 2016-07-01; 2016 除夕 is 7 Feb).
    cny_val = df[df["split"].eq("val") & df["is_chinese_new_year"].eq(1)]
    cny_note = {
        "test_cny_hours": int((df["split"].eq("test") & df["is_chinese_new_year"].eq(1)).sum()),
        "val_cny_hours": int(len(cny_val)),
        "val_cny": _slice_summary(cny_val),
        "note": (
            "Locked test is 2016-07-01 to 2016-12-31, so winter-test is December only "
            "and contains no 除夕/春节. The 2016 firework window is in validation."
        ),
    }

    pd.DataFrame(bins_actual).to_csv(OUT / "signed_error_by_actual_bin_winter_test.csv", index=False)
    pd.DataFrame(bins_delta).to_csv(OUT / "signed_error_by_delta_winter_test.csv", index=False)
    pd.DataFrame(phases["test_winter"]).to_csv(OUT / "episode_phase_winter_test.csv", index=False)
    pd.DataFrame(phases["val_winter"]).to_csv(OUT / "episode_phase_winter_val.csv", index=False)
    neighbor_table.to_csv(OUT / "nearest_neighbors.csv", index=False)

    report = {
        "predictions": pred_path,
        "signed_error_definition": "prediction - actual; negative means underprediction",
        "rapid_rise_ug_m3": RAPID_RISE,
        "episode_rule": f"actual target PM2.5 >= {EPISODE_THRESHOLD} for >= {EPISODE_MIN_HOURS} clock hours",
        "summaries": summaries,
        "winter_test_by_actual_bin": bins_actual,
        "winter_test_by_actual_delta": bins_delta,
        "episode_phases": phases,
        "neighbor_lead_on_rapid_rise": lead,
        "cny_coverage": cny_note,
        "test_winter_months": sorted(winter_test["event_time_local"].dt.month.unique().tolist()),
    }
    (OUT / "diagnosis.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "predictions": pred_path,
        "test": summaries["test"],
        "test_winter": summaries["test_winter"],
        "test_heating_statutory": summaries["test_heating_statutory"],
        "val_winter": summaries["val_winter"],
        "neighbor_lead_test_winter": lead["test_winter"],
        "cny": cny_note["note"],
        "test_cny_hours": cny_note["test_cny_hours"],
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
