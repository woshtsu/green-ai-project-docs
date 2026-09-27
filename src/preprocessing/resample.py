"""Resample irregular or high-frequency windows to the model frequency.

Empty bins are dropped. They are never filled with zero.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.data.schema import ORIGIN_COLUMN, QUALITY_COLUMN, TARGET_COLUMN, TIMESTAMP_COLUMN
from src.exceptions import ValidationError
from src.preprocessing.temporal import parse_horizon


def resample_to_frequency(
    frame: pd.DataFrame,
    expected_frequency: str,
) -> tuple[pd.DataFrame, bool, list[str]]:
    """Downsample to expected_frequency when the observed cadence is faster."""
    if frame.empty or TIMESTAMP_COLUMN not in frame.columns:
        return frame, False, []
    if len(frame) < 2:
        return frame, False, []

    expected = parse_horizon(expected_frequency)
    ordered = frame.sort_values(TIMESTAMP_COLUMN).copy()
    diffs = ordered[TIMESTAMP_COLUMN].diff().dropna()
    if diffs.empty:
        return frame, False, []
    observed = diffs.median()
    if pd.isna(observed) or observed <= pd.Timedelta(0):
        raise ValidationError("Cannot resample a series with an invalid frequency")
    if observed >= expected * 0.8:
        return frame.reset_index(drop=True), False, []

    numeric_columns = [
        column
        for column in ordered.columns
        if column not in {TIMESTAMP_COLUMN, ORIGIN_COLUMN, QUALITY_COLUMN}
        and pd.api.types.is_numeric_dtype(ordered[column])
    ]
    indexed = ordered.set_index(TIMESTAMP_COLUMN)
    aggregated = indexed[numeric_columns].resample(expected).mean()
    origin = _resample_label(indexed, ORIGIN_COLUMN, expected, default="unknown")
    quality = _resample_label(indexed, QUALITY_COLUMN, expected, default="ok")
    combined = aggregated.join(origin).join(quality)
    combined = combined.dropna(subset=[TARGET_COLUMN] if TARGET_COLUMN in combined.columns else []).reset_index()
    notes = [
        (
            f"Resampled observed cadence {observed} to {expected_frequency}. "
            "Empty bins were dropped and were not filled with zero."
        )
    ]
    return combined, True, notes


def _resample_label(
    indexed: pd.DataFrame,
    column: str,
    expected: pd.Timedelta,
    default: str,
) -> pd.Series:
    if column not in indexed.columns:
        empty = pd.Series(default, index=indexed.resample(expected).mean().index, name=column)
        return empty
    series = (
        indexed[column]
        .resample(expected)
        .agg(lambda values: _first_valid(values, default))
        .rename(column)
    )
    return series


def _first_valid(values: Any, default: str) -> str:
    series = pd.Series(values).dropna()
    if series.empty:
        return default
    return str(series.iloc[-1])
