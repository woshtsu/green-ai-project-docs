"""Temporal frequency, target horizon steps and chronological splits."""

from __future__ import annotations

import logging
import math
import re
from typing import Any

import pandas as pd

from src.data.schema import TIMESTAMP_COLUMN
from src.exceptions import InsufficientDataError, LeakageError, ValidationError

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
    """Compute N for shift(-N). Horizon must be an exact multiple of frequency."""
    horizon_delta = parse_horizon(horizon)
    if frequency <= pd.Timedelta(0):
        raise ValidationError("Frequency must be positive")
    ratio = horizon_delta / frequency
    if not math.isclose(ratio, round(ratio), rel_tol=0.0, abs_tol=1e-9):
        raise ValidationError(
            f"Horizon {horizon} is not an exact multiple of frequency {frequency}",
            details={
                "horizon": horizon,
                "frequency": str(frequency),
                "ratio": float(ratio),
            },
        )
    steps = int(round(ratio))
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


def target_timestamps(frame: pd.DataFrame, horizon: str) -> pd.Series:
    return pd.to_datetime(frame[TIMESTAMP_COLUMN], utc=True) + parse_horizon(horizon)


def assert_purged_boundaries(
    train: pd.DataFrame,
    validation: pd.DataFrame,
    test: pd.DataFrame,
    horizon: str,
) -> None:
    """Require max(target_time of previous) < min(feature_time of next)."""
    _assert_boundary(train, validation, horizon, "TRAIN", "VALIDATION")
    _assert_boundary(validation, test, horizon, "VALIDATION", "TEST")


def _assert_boundary(previous: pd.DataFrame, following: pd.DataFrame, horizon: str, left: str, right: str) -> None:
    max_target = target_timestamps(previous, horizon).max()
    min_feature = pd.to_datetime(following[TIMESTAMP_COLUMN], utc=True).min()
    if max_target >= min_feature:
        raise LeakageError(
            f"Partition boundary {left}|{right} is not purged for horizon {horizon}",
            details={
                "max_previous_target_time": str(max_target),
                "min_next_feature_time": str(min_feature),
                "horizon": horizon,
            },
        )


def purge_horizon_boundaries(
    train: pd.DataFrame,
    validation: pd.DataFrame,
    test: pd.DataFrame,
    horizon: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Drop trailing rows whose target already falls inside the next partition."""
    val_start = pd.to_datetime(validation[TIMESTAMP_COLUMN], utc=True).min()
    test_start = pd.to_datetime(test[TIMESTAMP_COLUMN], utc=True).min()
    train_kept = train.loc[target_timestamps(train, horizon) < val_start].copy()
    validation_kept = validation.loc[target_timestamps(validation, horizon) < test_start].copy()
    test_kept = test.copy()
    if train_kept.empty or validation_kept.empty or test_kept.empty:
        raise InsufficientDataError(
            "INSUFFICIENT_DATA: horizon purge emptied a partition",
            details={
                "code": "INSUFFICIENT_DATA",
                "available_records": {
                    "train": int(len(train_kept)),
                    "validation": int(len(validation_kept)),
                    "test": int(len(test_kept)),
                },
                "horizon": horizon,
                "reason": "purging at least one forecast horizon at each split boundary",
            },
        )
    assert_purged_boundaries(train_kept, validation_kept, test_kept, horizon)
    LOGGER.info(
        "Purged split train=%s validation=%s test=%s horizon=%s",
        len(train_kept),
        len(validation_kept),
        len(test_kept),
        horizon,
    )
    return train_kept.reset_index(drop=True), validation_kept.reset_index(drop=True), test_kept.reset_index(drop=True)


def temporal_split(
    frame: pd.DataFrame,
    train_ratio: float = 0.70,
    validation_ratio: float = 0.15,
    test_ratio: float = 0.15,
    horizon: str | None = None,
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
    if horizon:
        return purge_horizon_boundaries(train, validation, test, horizon)
    return train, validation, test


def _period(frame: pd.DataFrame) -> dict[str, Any] | None:
    if frame.empty or TIMESTAMP_COLUMN not in frame.columns:
        return None
    return {
        "start": str(frame[TIMESTAMP_COLUMN].min()),
        "end": str(frame[TIMESTAMP_COLUMN].max()),
    }
