"""Temporal frequency, target horizon steps and chronological splits."""

from __future__ import annotations

import logging
import re
from typing import Any

import pandas as pd

from src.data.schema import TIMESTAMP_COLUMN
from src.exceptions import InsufficientDataError, ValidationError

LOGGER = logging.getLogger(__name__)

HORIZON_PATTERN = re.compile(r"^(?P<value>\d+)(?P<unit>[smhd])$", re.IGNORECASE)

UNIT_TO_SECONDS = {
    "s": 1,
    "m": 60,
    "h": 3600,
    "d": 86400,
}


def parse_horizon(horizon: str) -> pd.Timedelta:
    match = HORIZON_PATTERN.match(str(horizon).strip())
    if not match:
        raise ValidationError(f"Unsupported horizon format: {horizon}")
    seconds = int(match.group("value")) * UNIT_TO_SECONDS[match.group("unit").lower()]
    return pd.Timedelta(seconds=seconds)


def infer_frequency(timestamps: pd.Series) -> pd.Timedelta:
    ordered = pd.to_datetime(timestamps, utc=True).sort_values()
    diffs = ordered.diff().dropna()
    if diffs.empty:
        raise InsufficientDataError(
            "INSUFFICIENT_DATA: cannot infer frequency",
            details={
                "code": "INSUFFICIENT_DATA",
                "available_records": int(len(timestamps)),
                "period": None,
                "frequency": None,
                "horizon": None,
                "reason": "need at least two timestamps to infer frequency",
            },
        )
    frequency = diffs.median()
    if pd.isna(frequency) or frequency <= pd.Timedelta(0):
        raise ValidationError("Inferred frequency is invalid")
    return frequency


def horizon_steps(horizon: str, frequency: pd.Timedelta) -> int:
    """Compute N for shift(-N) from the real sampling frequency."""
    horizon_delta = parse_horizon(horizon)
    if frequency <= pd.Timedelta(0):
        raise ValidationError("Frequency must be positive")
    steps = int(round(horizon_delta / frequency))
    if steps < 1:
        raise InsufficientDataError(
            "INSUFFICIENT_DATA: horizon is shorter than sampling frequency",
            details={
                "code": "INSUFFICIENT_DATA",
                "available_records": None,
                "period": None,
                "frequency": str(frequency),
                "horizon": horizon,
                "reason": "horizon / frequency < 1 step",
            },
        )
    return steps


def assign_segments(frame: pd.DataFrame, frequency: pd.Timedelta) -> pd.DataFrame:
    """Mark contiguous temporal segments so lags do not cross gaps."""
    result = frame.sort_values(TIMESTAMP_COLUMN).copy()
    diffs = result[TIMESTAMP_COLUMN].diff()
    result["_segment"] = (diffs > frequency * 1.5).cumsum()
    return result


def temporal_split(
    frame: pd.DataFrame,
    train_ratio: float = 0.70,
    validation_ratio: float = 0.15,
    test_ratio: float = 0.15,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Chronological TRAIN | VALIDATION | TEST split. Never shuffles."""
    if abs((train_ratio + validation_ratio + test_ratio) - 1.0) > 1e-9:
        raise ValidationError("Split ratios must sum to 1.0")
    if TIMESTAMP_COLUMN not in frame.columns:
        raise ValidationError("Cannot split without timestamps")

    ordered = frame.sort_values(TIMESTAMP_COLUMN).reset_index(drop=True)
    n_rows = len(ordered)
    if n_rows < 3:
        raise InsufficientDataError(
            "INSUFFICIENT_DATA: not enough rows for temporal split",
            details={
                "code": "INSUFFICIENT_DATA",
                "available_records": n_rows,
                "period": _period(ordered),
                "frequency": None,
                "horizon": None,
                "reason": "need at least 3 rows after feature engineering",
            },
        )

    train_end = int(n_rows * train_ratio)
    valid_end = train_end + int(n_rows * validation_ratio)
    if valid_end <= train_end:
        valid_end = min(train_end + 1, n_rows - 1)
    if train_end < 1 or valid_end <= train_end or valid_end >= n_rows:
        raise InsufficientDataError(
            "INSUFFICIENT_DATA: temporal split produced an empty partition",
            details={
                "code": "INSUFFICIENT_DATA",
                "available_records": n_rows,
                "period": _period(ordered),
                "frequency": None,
                "horizon": None,
                "reason": f"split bounds train_end={train_end} valid_end={valid_end} n={n_rows}",
            },
        )

    train = ordered.iloc[:train_end].copy()
    validation = ordered.iloc[train_end:valid_end].copy()
    test = ordered.iloc[valid_end:].copy()
    if train.empty or validation.empty or test.empty:
        raise InsufficientDataError(
            "INSUFFICIENT_DATA: a temporal partition is empty",
            details={
                "code": "INSUFFICIENT_DATA",
                "available_records": n_rows,
                "period": _period(ordered),
                "frequency": None,
                "horizon": None,
                "reason": "empty train, validation or test partition",
            },
        )
    LOGGER.info(
        "Temporal split train=%s validation=%s test=%s",
        len(train),
        len(validation),
        len(test),
    )
    return train, validation, test


def _period(frame: pd.DataFrame) -> dict[str, Any] | None:
    if frame.empty or TIMESTAMP_COLUMN not in frame.columns:
        return None
    return {
        "start": str(frame[TIMESTAMP_COLUMN].min()),
        "end": str(frame[TIMESTAMP_COLUMN].max()),
    }
