"""Data-quality flags and quarantine split for UCI processed data (Phase 4)."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.processing.schema import (
    CANONICAL_OUTPUT_COLUMNS,
    DQ_FLAG_COLUMNS,
    NATURAL_KEY_COLUMNS,
    NON_NEGATIVE_COLUMNS,
    POLLUTANT_COLUMNS,
    SUSPECT_CAP_VALUES,
    WEATHER_COLUMNS,
)


@dataclass(frozen=True)
class DQResult:
    clean: pd.DataFrame
    quarantine: pd.DataFrame
    quarantine_row_count: int
    suspect_cap_row_count: int
    missing_pollutant_row_count: int
    missing_weather_row_count: int


def _invalid_negative_mask(df: pd.DataFrame) -> pd.Series:
    mask = pd.Series(False, index=df.index)
    for col in NON_NEGATIVE_COLUMNS:
        if col not in df.columns:
            continue
        mask = mask | (df[col].notna() & (df[col] < 0))
    return mask


def _assert_no_duplicates(df: pd.DataFrame) -> None:
    dup = df.duplicated(subset=list(NATURAL_KEY_COLUMNS), keep=False)
    if dup.any():
        sample = df.loc[dup, list(NATURAL_KEY_COLUMNS)].head(5)
        raise ValueError(
            "Duplicate natural key (station_name, event_time_local) detected; "
            f"count={int(dup.sum())}; sample=\n{sample.to_string(index=False)}"
        )


def _suspect_cap_mask(df: pd.DataFrame) -> pd.Series:
    mask = pd.Series(False, index=df.index)
    for col, values in SUSPECT_CAP_VALUES.items():
        if col not in df.columns:
            continue
        mask = mask | df[col].isin(values)
    return mask


def apply_data_quality(df: pd.DataFrame) -> DQResult:
    """
    Enforce duplicate policy, quarantine invalid negatives, attach DQ flags.

    No imputation. Extreme round caps stay in clean set with suspect_cap=True.
    """
    working = df.copy()
    _assert_no_duplicates(working)

    neg_mask = _invalid_negative_mask(working)
    quarantine = working.loc[neg_mask].copy()
    clean = working.loc[~neg_mask].copy()

    if not quarantine.empty:
        quarantine["has_missing_pollutant"] = False
        quarantine["has_missing_weather"] = False
        quarantine["suspect_cap"] = False
        quarantine["data_quality_status"] = "QUARANTINED_NEGATIVE"
        quarantine["quarantine_reason"] = "invalid_negative"

    if clean.empty:
        empty_clean = clean
        for col in DQ_FLAG_COLUMNS:
            if col not in empty_clean.columns:
                empty_clean[col] = pd.Series(dtype="boolean" if col != "data_quality_status" else "string")
        return DQResult(
            clean=_order_columns(empty_clean),
            quarantine=_order_quarantine(quarantine),
            quarantine_row_count=len(quarantine),
            suspect_cap_row_count=0,
            missing_pollutant_row_count=0,
            missing_weather_row_count=0,
        )

    has_missing_pollutant = clean[list(POLLUTANT_COLUMNS)].isna().any(axis=1)
    has_missing_weather = clean[list(WEATHER_COLUMNS)].isna().any(axis=1)
    suspect_cap = _suspect_cap_mask(clean)

    clean["has_missing_pollutant"] = has_missing_pollutant
    clean["has_missing_weather"] = has_missing_weather
    clean["suspect_cap"] = suspect_cap

    status = pd.Series("OK", index=clean.index, dtype="string")
    status = status.mask(has_missing_pollutant | has_missing_weather, "MISSING_MEASUREMENT")
    status = status.mask(suspect_cap, "SUSPECT_CAP")
    clean["data_quality_status"] = status

    return DQResult(
        clean=_order_columns(clean),
        quarantine=_order_quarantine(quarantine),
        quarantine_row_count=len(quarantine),
        suspect_cap_row_count=int(suspect_cap.sum()),
        missing_pollutant_row_count=int(has_missing_pollutant.sum()),
        missing_weather_row_count=int(has_missing_weather.sum()),
    )


def _order_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in CANONICAL_OUTPUT_COLUMNS if c in df.columns]
    extras = [c for c in df.columns if c not in cols]
    return df[cols + extras].reset_index(drop=True)


def _order_quarantine(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.reset_index(drop=True)
    preferred = [c for c in CANONICAL_OUTPUT_COLUMNS if c in df.columns]
    extras = [c for c in df.columns if c not in preferred]
    return df[preferred + extras].reset_index(drop=True)
