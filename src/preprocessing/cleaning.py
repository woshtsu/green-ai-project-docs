"""Cleaning that preserves missingness and origin.

Never converts null / NaN / missing / no_data into 0.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from src.data.schema import ORIGIN_COLUMN, QUALITY_COLUMN, TARGET_COLUMN, TIMESTAMP_COLUMN
from src.exceptions import ValidationError

LOGGER = logging.getLogger(__name__)

MISSING_TOKENS = {"", "null", "none", "nan", "missing", "no_data", "n/a"}


def clean_dataset(frame: pd.DataFrame) -> pd.DataFrame:
    """Sort, normalize timestamps and canonicalize missing tokens without imputation."""
    if frame.empty:
        raise ValidationError("Cannot clean an empty dataset")

    cleaned = frame.copy()
    cleaned[TIMESTAMP_COLUMN] = pd.to_datetime(cleaned[TIMESTAMP_COLUMN], errors="coerce")
    if cleaned[TIMESTAMP_COLUMN].isna().any():
        raise ValidationError("Cleaning found invalid timestamps")
    if getattr(cleaned[TIMESTAMP_COLUMN].dt, "tz", None) is None:
        raise ValidationError("Timestamps must include a timezone; naive values were not localized")
    cleaned[TIMESTAMP_COLUMN] = cleaned[TIMESTAMP_COLUMN].dt.tz_convert("UTC")

    cleaned = cleaned.sort_values(TIMESTAMP_COLUMN).reset_index(drop=True)

    numeric_candidates = [
        column
        for column in cleaned.columns
        if column not in {TIMESTAMP_COLUMN, ORIGIN_COLUMN, QUALITY_COLUMN}
    ]
    for column in numeric_candidates:
        cleaned[column] = _canonicalize_numeric(cleaned[column])

    inf_mask = cleaned[numeric_candidates].isin([np.inf, -np.inf])
    if inf_mask.any().any():
        raise ValidationError("Infinite values cannot be cleaned automatically")

    if TARGET_COLUMN in cleaned.columns and cleaned[TARGET_COLUMN].isna().any():
        raise ValidationError("Target contains missing values; they were not imputed to zero")

    LOGGER.info("Cleaned dataset with %s records", len(cleaned))
    return cleaned


def _canonicalize_numeric(series: pd.Series) -> pd.Series:
    if series.dtype == object:
        normalized = series.map(_token_to_nan)
        return pd.to_numeric(normalized, errors="coerce")
    return pd.to_numeric(series, errors="coerce")


def _token_to_nan(value: object) -> object:
    if value is None:
        return np.nan
    if isinstance(value, str) and value.strip().lower() in MISSING_TOKENS:
        return np.nan
    return value
