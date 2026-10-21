"""Forecast-time reliability flags. This is an evaluation layer, not a model.

Every flag uses only quantities that exist at the origin hour. The next hour's
PM2.5 is not an input. Cuts are the project's existing round numbers, not a
search:

- fast change: absolute PM2.5 change over the previous hour, at least 20 µg/m³
- spatial gap: absolute gap between the station and the median of its three
  nearest neighbors at the same hour, at least 50 µg/m³
- anomalous input: the frozen causal suspect flag
- episode: the locked in-episode flag (PM2.5 at least 115 for at least 3 hours
  ending now)

A single high hour (PM2.5 at least 115) is reported as a reference. It is not
one of the candidate flags.

A large error is an absolute error of at least 50 µg/m³. The 30 µg/m³ count is
a sensitivity and does not change the decision. A candidate is kept only when
the same flag meets the bar on train and on validation. Test is refused.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

FAST_CHANGE_UG = 20.0
SPATIAL_GAP_UG = 50.0
HIGH_NOW_UG = 115.0
PRIMARY_ERROR_UG = 50.0
SENSITIVITY_ERROR_UG = 30.0

MIN_FLAGGED = 30
MAX_FLAG_RATE = 0.20
MIN_RECALL = 0.25
MIN_LIFT = 2.0

CANDIDATE_FLAGS: tuple[str, ...] = (
    "flag_fast_change",
    "flag_spatial_gap",
    "flag_suspect_causal",
    "flag_in_episode",
    "flag_any_visible",
)
REFERENCE_FLAGS: tuple[str, ...] = ("flag_high_now",)
CONFIRMATION_SPLITS = frozenset({"train", "val"})


def assert_confirmation_frame(df: pd.DataFrame) -> None:
    """Reliability scores are train and validation only."""
    if "split" not in df.columns:
        raise KeyError("split")
    found = set(df["split"].astype(str))
    extra = found - CONFIRMATION_SPLITS
    if extra:
        raise ValueError(f"reliability scoring refuses splits other than train and val: {sorted(extra)}")
    if not found:
        raise ValueError("reliability frame is empty")


def add_visible_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Boolean flags known at the origin hour. The target column is not read."""
    required = (
        "pm25_ug_m3",
        "pm25_delta_1",
        "spatial_gradient_median",
        "suspect_spatiotemporal_causal",
        "in_episode_flag",
    )
    missing = [name for name in required if name not in df.columns]
    if missing:
        raise KeyError(f"add_visible_flags requires {missing}")
    out = df.copy()
    fast = pd.to_numeric(out["pm25_delta_1"], errors="coerce").abs().ge(FAST_CHANGE_UG)
    gap = pd.to_numeric(out["spatial_gradient_median"], errors="coerce").abs().ge(SPATIAL_GAP_UG)
    suspect = out["suspect_spatiotemporal_causal"].fillna(False).astype(bool)
    episode = pd.to_numeric(out["in_episode_flag"], errors="coerce").fillna(0).ge(1)
    high = pd.to_numeric(out["pm25_ug_m3"], errors="coerce").ge(HIGH_NOW_UG)
    out["flag_fast_change"] = fast.fillna(False).to_numpy(dtype=bool)
    out["flag_spatial_gap"] = gap.fillna(False).to_numpy(dtype=bool)
    out["flag_suspect_causal"] = suspect.to_numpy(dtype=bool)
    out["flag_in_episode"] = episode.fillna(False).to_numpy(dtype=bool)
    out["flag_high_now"] = high.fillna(False).to_numpy(dtype=bool)
    out["flag_any_visible"] = (
        out["flag_fast_change"]
        | out["flag_spatial_gap"]
        | out["flag_suspect_causal"]
        | out["flag_in_episode"]
    )
    return out


def score_flag(abs_error: np.ndarray, flag: np.ndarray, *, cut: float) -> dict[str, float | int | bool]:
    """Precision and recall of hours whose absolute error is at least `cut`."""
    error = np.asarray(abs_error, dtype=float)
    marked = np.asarray(flag, dtype=bool)
    if error.shape != marked.shape:
        raise ValueError("absolute error and flag must have the same shape")
    if error.size and not np.isfinite(error).all():
        raise ValueError("absolute error must be finite")
    large = error >= cut
    n = int(error.size)
    n_flagged = int(marked.sum())
    n_large = int(large.sum())
    hits = int((marked & large).sum())
    precision = hits / n_flagged if n_flagged else float("nan")
    recall = hits / n_large if n_large else float("nan")
    base_rate = n_large / n if n else float("nan")
    lift = precision / base_rate if base_rate and np.isfinite(precision) else float("nan")
    total = float(error.sum())
    score: dict[str, float | int | bool] = {
        "n": n,
        "n_flagged": n_flagged,
        "flag_rate": n_flagged / n if n else float("nan"),
        "n_large": n_large,
        "base_rate": base_rate,
        "hits": hits,
        "precision": precision,
        "recall": recall,
        "lift": lift,
        "mae_flagged": float(error[marked].mean()) if n_flagged else float("nan"),
        "mae_unflagged": float(error[~marked].mean()) if n_flagged < n else float("nan"),
        "error_mass_share": float(error[marked].sum() / total) if total else float("nan"),
    }
    score["meets_bar"] = meets_bar(score)
    return score


def meets_bar(score: dict[str, float | int | bool]) -> bool:
    """Selective warning: uncommon, and at least twice as precise as the base rate."""
    n_flagged = int(score["n_flagged"])
    if n_flagged < MIN_FLAGGED:
        return False
    flag_rate = float(score["flag_rate"])
    recall = float(score["recall"])
    precision = float(score["precision"])
    base_rate = float(score["base_rate"])
    if not np.isfinite(flag_rate) or flag_rate > MAX_FLAG_RATE:
        return False
    if not np.isfinite(recall) or recall < MIN_RECALL:
        return False
    if not np.isfinite(precision) or not np.isfinite(base_rate):
        return False
    return precision >= MIN_LIFT * base_rate


def decide(scores: list[dict]) -> dict[str, object]:
    """Keep a pre-registered flag only when train and validation both clear the bar.

    Rows whose outcome is not the primary 50 µg/m³ definition are ignored.
    """
    passed: list[str] = []
    for flag in CANDIDATE_FLAGS:
        by_split = {
            row["split"]: row
            for row in scores
            if row["flag"] == flag and row["outcome"] == "primary"
        }
        if set(by_split) != CONFIRMATION_SPLITS:
            raise ValueError(f"{flag} needs a primary score on train and on validation")
        if by_split["train"]["meets_bar"] and by_split["val"]["meets_bar"]:
            passed.append(flag)
    return {
        "decision": "RELIABILITY_FLAG" if passed else "CLOSE",
        "passed": passed,
        "lock_unchanged": True,
    }
