"""Dataset quality validation. Never converts missing values to zero."""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np
import pandas as pd

from src.data.schema import (
    ALLOWED_DATA_STATUS,
    ALLOWED_ORIGINS,
    ALLOWED_QUALITY,
    ORIGIN_COLUMN,
    QUALITY_COLUMN,
    REQUIRED_DATASET_FIELDS,
    REQUIRED_METADATA_FIELDS,
    REQUIRED_PERIOD_FIELDS,
    REQUIRED_RECORD_FIELDS,
    REQUIRED_RESOURCE_FIELDS,
    TARGET_COLUMN,
    TIMESTAMP_COLUMN,
)
from src.exceptions import InsufficientDataError, ValidationError

LOGGER = logging.getLogger(__name__)

NUMERIC_COLUMNS = (
    TARGET_COLUMN,
    "memory_utilization",
    "network_in",
    "network_out",
    "workload_count",
    "pod_count",
    "cpu_requests",
    "memory_requests",
)


def validate_dataset(frame: pd.DataFrame, metadata: dict[str, Any]) -> dict[str, Any]:
    """Validate contract, timestamps, quality and temporal continuity.

    Returns a report. Raises ValidationError or InsufficientDataError on blockers.
    """
    _validate_metadata(metadata)

    if frame is None or frame.empty:
        period = metadata.get("period") or {}
        raise InsufficientDataError(
            "INSUFFICIENT_DATA: empty dataset",
            details={
                "code": "INSUFFICIENT_DATA",
                "available_records": 0,
                "period": period,
                "frequency": None,
                "horizon": None,
                "reason": "dataset has no feature records",
            },
        )

    missing_cols = [col for col in REQUIRED_RECORD_FIELDS if col not in frame.columns]
    if missing_cols:
        raise ValidationError(
            f"Missing required columns: {missing_cols}",
            details={"missing_columns": missing_cols},
        )

    _validate_timestamps(frame)
    _validate_duplicates(frame)
    _validate_numeric_quality(frame)
    _validate_origin_and_quality(frame, metadata)

    frequency = _infer_frequency(frame[TIMESTAMP_COLUMN])
    gaps = _detect_gaps(frame[TIMESTAMP_COLUMN], frequency)
    report = {
        "valid": True,
        "records": int(len(frame)),
        "period": {
            "start": _iso(frame[TIMESTAMP_COLUMN].min()),
            "end": _iso(frame[TIMESTAMP_COLUMN].max()),
        },
        "frequency_seconds": frequency.total_seconds() if frequency is not None else None,
        "duplicate_timestamps": 0,
        "gap_count": len(gaps),
        "gaps": gaps[:20],
        "origins": sorted(frame[ORIGIN_COLUMN].dropna().astype(str).unique().tolist()),
        "missing_by_column": {
            col: int(frame[col].isna().sum()) for col in frame.columns if frame[col].isna().any()
        },
    }
    if gaps:
        LOGGER.warning("Detected %s temporal discontinuities", len(gaps))
    return report


def validate_payload(payload: dict[str, Any]) -> None:
    """Validate the raw Data Processing JSON contract before framing records."""
    missing = [field for field in REQUIRED_DATASET_FIELDS if field not in payload]
    if missing:
        raise ValidationError(
            f"Dataset payload missing required fields: {missing}",
            details={"missing_fields": missing},
        )
    if not isinstance(payload.get("features"), list):
        raise ValidationError("Dataset field 'features' must be a list")


def _validate_metadata(metadata: dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_METADATA_FIELDS if field not in metadata or metadata[field] is None]
    if missing:
        raise ValidationError(
            f"Dataset metadata missing required fields: {missing}",
            details={"missing_fields": missing},
        )

    period = metadata.get("period") or {}
    if not isinstance(period, dict):
        raise ValidationError("period must be an object")
    missing_period = [field for field in REQUIRED_PERIOD_FIELDS if field not in period]
    if missing_period:
        raise ValidationError(f"period missing fields: {missing_period}")

    resource = metadata.get("resource") or {}
    if not isinstance(resource, dict):
        raise ValidationError("resource must be an object")
    missing_resource = [field for field in REQUIRED_RESOURCE_FIELDS if field not in resource]
    if missing_resource:
        raise ValidationError(f"resource missing fields: {missing_resource}")

    data_status = metadata.get("dataStatus")
    if data_status not in ALLOWED_DATA_STATUS:
        raise ValidationError(
            f"Invalid dataStatus '{data_status}'",
            details={"allowed": sorted(ALLOWED_DATA_STATUS)},
        )

    origins = metadata.get("origins")
    if not isinstance(origins, list) or not origins:
        raise ValidationError("origins must be a non-empty list")
    invalid_origins = [item for item in origins if item not in ALLOWED_ORIGINS]
    if invalid_origins:
        raise ValidationError(
            f"Invalid dataset origins: {invalid_origins}",
            details={"allowed": sorted(ALLOWED_ORIGINS)},
        )


def _validate_timestamps(frame: pd.DataFrame) -> None:
    series = frame[TIMESTAMP_COLUMN]
    if series.isna().any():
        raise ValidationError(
            "Invalid timestamps detected",
            details={"invalid_count": int(series.isna().sum())},
        )
    if getattr(series.dt, "tz", None) is None:
        raise ValidationError("Timestamps must include a timezone")

    if not series.is_monotonic_increasing:
        ordered = series.sort_values()
        if not ordered.equals(series.reset_index(drop=True)) and series.tolist() != sorted(series.tolist()):
            LOGGER.info("Timestamps are not pre-sorted; validation allows this and cleaning will sort")


def _validate_duplicates(frame: pd.DataFrame) -> None:
    duplicates = int(frame[TIMESTAMP_COLUMN].duplicated().sum())
    if duplicates:
        raise ValidationError(
            "Duplicate timestamps are not allowed",
            details={"duplicate_count": duplicates},
        )


def _validate_numeric_quality(frame: pd.DataFrame) -> None:
    for column in NUMERIC_COLUMNS:
        if column not in frame.columns:
            continue
        series = pd.to_numeric(frame[column], errors="coerce")
        if column == TARGET_COLUMN and series.isna().any() and frame[column].isna().any():
            raise ValidationError(
                f"Missing values in required column '{column}'",
                details={"column": column, "missing": int(frame[column].isna().sum())},
            )
        values = frame[column]
        if values.map(_is_inf).any():
            raise ValidationError(
                f"Infinite values are not allowed in '{column}'",
                details={"column": column},
            )
        if column == TARGET_COLUMN and series.isna().any():
            raise ValidationError(
                f"NaN values are not allowed in '{column}'",
                details={"column": column},
            )


def _validate_origin_and_quality(frame: pd.DataFrame, metadata: dict[str, Any]) -> None:
    invalid_origin = sorted(
        {str(item) for item in frame[ORIGIN_COLUMN].dropna().unique() if item not in ALLOWED_ORIGINS}
    )
    if invalid_origin:
        raise ValidationError(
            f"Invalid origin values: {invalid_origin}",
            details={"allowed": sorted(ALLOWED_ORIGINS)},
        )

    invalid_quality = sorted(
        {str(item) for item in frame[QUALITY_COLUMN].dropna().unique() if item not in ALLOWED_QUALITY}
    )
    if invalid_quality:
        raise ValidationError(
            f"Invalid quality values: {invalid_quality}",
            details={"allowed": sorted(ALLOWED_QUALITY)},
        )

    declared = set(metadata.get("origins") or [])
    observed = set(frame[ORIGIN_COLUMN].dropna().astype(str).unique())
    if not observed.issubset(declared):
        raise ValidationError(
            "Record origins are not declared in dataset metadata",
            details={"declared": sorted(declared), "observed": sorted(observed)},
        )


def _infer_frequency(timestamps: pd.Series) -> pd.Timedelta | None:
    diffs = timestamps.sort_values().diff().dropna()
    if diffs.empty:
        return None
    return diffs.median()


def _detect_gaps(timestamps: pd.Series, frequency: pd.Timedelta | None) -> list[dict[str, Any]]:
    if frequency is None or pd.isna(frequency) or frequency <= pd.Timedelta(0):
        return []
    ordered = timestamps.sort_values().reset_index(drop=True)
    diffs = ordered.diff()
    threshold = frequency * 1.5
    gaps: list[dict[str, Any]] = []
    for idx in diffs[diffs > threshold].index:
        gaps.append(
            {
                "from": _iso(ordered.iloc[idx - 1]),
                "to": _iso(ordered.iloc[idx]),
                "delta_seconds": float(diffs.iloc[idx].total_seconds()),
            }
        )
    return gaps


def _is_inf(value: Any) -> bool:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return False
    try:
        return bool(np.isinf(value))
    except (TypeError, ValueError):
        return False


def _iso(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    return timestamp.isoformat()
