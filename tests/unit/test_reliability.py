"""Reliability flags use the origin hour only and a bar frozen before validation."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.forecasting.reliability import (
    add_visible_flags,
    assert_confirmation_frame,
    decide,
    meets_bar,
    score_flag,
)

MODULE_PATH = Path(__file__).resolve().parents[2] / "src" / "forecasting" / "reliability.py"


def _row(**overrides) -> dict:
    base = {
        "pm25_ug_m3": 40.0,
        "pm25_delta_1": 0.0,
        "spatial_gradient_median": 0.0,
        "suspect_spatiotemporal_causal": False,
        "in_episode_flag": 0,
        "y_pm25_tplus1": 999.0,
    }
    base.update(overrides)
    return base


def test_rule_module_has_no_held_out_date_or_target_lookup():
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "2016-12-20" not in text
    assert "y_pm25_tplus1" not in text


def test_flags_ignore_the_next_hour_and_a_single_high_hour():
    frame = pd.DataFrame(
        [
            _row(pm25_delta_1=19.9, y_pm25_tplus1=1.0),
            _row(pm25_delta_1=20.0),
            _row(pm25_delta_1=-50.0),
            _row(spatial_gradient_median=50.0),
            _row(spatial_gradient_median=np.nan),
            _row(pm25_ug_m3=200.0, in_episode_flag=0),
            _row(pm25_ug_m3=200.0, in_episode_flag=1),
            _row(suspect_spatiotemporal_causal=True),
        ]
    )
    flagged = add_visible_flags(frame)
    assert flagged["flag_fast_change"].tolist() == [
        False,
        True,
        True,
        False,
        False,
        False,
        False,
        False,
    ]
    assert flagged["flag_spatial_gap"].tolist()[3:5] == [True, False]
    assert bool(flagged.loc[5, "flag_high_now"])
    assert not bool(flagged.loc[5, "flag_any_visible"])
    assert bool(flagged.loc[6, "flag_any_visible"])
    assert bool(flagged.loc[7, "flag_any_visible"])
    assert flagged["flag_any_visible"].tolist() == [
        False,
        True,
        True,
        True,
        False,
        False,
        True,
        True,
    ]


def test_confirmation_frame_refuses_the_held_out_split():
    with pytest.raises(ValueError, match="refuses"):
        assert_confirmation_frame(pd.DataFrame({"split": ["train", "test"]}))


def test_bar_requires_a_selective_double_base_rate():
    error = np.array([60.0] * 100 + [10.0] * 900)
    marked = np.array([True] * 80 + [False] * 20 + [True] * 40 + [False] * 860)
    score = score_flag(error, marked, cut=50.0)
    assert score["n_flagged"] == 120
    assert score["hits"] == 80
    assert score["recall"] == pytest.approx(0.80)
    assert score["precision"] == pytest.approx(80 / 120)
    assert score["lift"] == pytest.approx((80 / 120) / 0.10)
    assert meets_bar(score)

    wide = score_flag(error, np.array([True] * 300 + [False] * 700), cut=50.0)
    assert not meets_bar(wide)

    rare = score_flag(error, np.array([True] * 20 + [False] * 980), cut=50.0)
    assert not meets_bar(rare)


def test_decision_uses_only_the_primary_outcome_on_both_splits():
    def row(split: str, flag: str, passed: bool, outcome: str = "primary") -> dict:
        return {"split": split, "flag": flag, "outcome": outcome, "meets_bar": passed}

    flags = [
        "flag_fast_change",
        "flag_spatial_gap",
        "flag_suspect_causal",
        "flag_in_episode",
        "flag_any_visible",
    ]
    scores = []
    for flag in flags:
        scores.append(row("train", flag, False))
        scores.append(row("val", flag, False))
    scores.append(row("train", "flag_fast_change", True, outcome="sensitivity"))
    scores.append(row("val", "flag_fast_change", True, outcome="sensitivity"))
    assert decide(scores)["decision"] == "CLOSE"

    scores = [row(split, flag, flag == "flag_spatial_gap") for flag in flags for split in ("train", "val")]
    decided = decide(scores)
    assert decided["decision"] == "RELIABILITY_FLAG"
    assert decided["passed"] == ["flag_spatial_gap"]
    assert decided["lock_unchanged"] is True
