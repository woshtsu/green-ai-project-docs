"""Adapt external Data Processing / spec payloads to the internal ML dataset.

The ML component never asks other services to change their JSON.
Differences are resolved here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from src.data.schema import (
    ALLOWED_ORIGINS,
    BLOCKING_DATA_STATUS,
    EXPECTED_FREQUENCY,
    FEATURE_NAME_ALIASES,
    PERCENT_COLUMNS,
    QUALITY_ALIASES,
    RATIO_UNITS,
    SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
    TARGET_COLUMN,
    TIMESTAMP_COLUMN,
)
from src.exceptions import DatasetError, InsufficientDataError, ValidationError
from src.preprocessing.resample import resample_to_frequency


@dataclass
class AdaptedDataset:
    """Normalized internal dataset produced from an external contract."""

    payload: dict[str, Any]
    frame: pd.DataFrame
    metadata: dict[str, Any]
    source_format: str
    resampled: bool = False
    warnings: list[str] = field(default_factory=list)


def adapt_input(
    payload: dict[str, Any],
    *,
    strict: bool = False,
    expected_frequency: str | None = EXPECTED_FREQUENCY,
) -> AdaptedDataset:
    """Convert an external JSON contract into internal temporal records."""
    if not isinstance(payload, dict):
        raise ValidationError(
            "Input payload must be a JSON object",
            details={"code": "INVALID_INPUT"},
        )

    version = payload.get("schemaVersion", SCHEMA_VERSION)
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        raise ValidationError(
            f"Unsupported schemaVersion '{version}'",
            details={"code": "INVALID_INPUT", "supported": sorted(SUPPORTED_SCHEMA_VERSIONS)},
        )

    data_status = payload.get("dataStatus")
    if data_status in BLOCKING_DATA_STATUS:
        raise DatasetError(
            "Dataset has no usable observations",
            details={
                "code": "INVALID_DATASET",
                "dataStatus": data_status,
                "reason": "no_data is not converted to zero",
            },
        )

    features = payload.get("features")
    if features is None:
        raise ValidationError(
            "Dataset field 'features' is required",
            details={"code": "INVALID_INPUT"},
        )
    if not isinstance(features, list):
        raise ValidationError(
            "Dataset field 'features' must be a list",
            details={"code": "INVALID_INPUT"},
        )
    if len(features) == 0:
        raise DatasetError(
            "Dataset features are empty",
            details={"code": "INVALID_DATASET", "reason": "empty feature list"},
        )

    if _is_name_value_unit(features):
        records, source_format = _from_name_value_unit(features, payload), "name_value_unit"
    elif _is_temporal_record(features):
        records, source_format = _from_temporal_records(features, payload), "temporal_records"
    else:
        raise ValidationError(
            "Unsupported feature format. Expected temporal records or name/value/unit objects.",
            details={"code": "INVALID_INPUT"},
        )

    frame = pd.DataFrame(records)
    if frame.empty:
        raise DatasetError(
            "Adapter produced an empty dataset",
            details={"code": "INVALID_DATASET"},
        )

    frame = _normalize_frame(frame, payload)
    warnings = list(payload.get("warnings") or [])
    warnings.append("Adapted inside ML. External contracts were not modified.")

    resampled = False
    if expected_frequency:
        frame, did_resample, resample_notes = resample_to_frequency(frame, expected_frequency)
        resampled = did_resample
        warnings.extend(resample_notes)
        if frame.empty:
            raise InsufficientDataError(
                "Resampling removed every observation; empty bins were not filled with zero",
                details={"code": "INVALID_DATASET", "frequency": expected_frequency},
            )

    metadata = _build_metadata(payload, frame, warnings, strict=strict)
    normalized = {
        "schemaVersion": metadata["schemaVersion"],
        "datasetId": metadata["datasetId"],
        "period": metadata["period"],
        "resource": metadata["resource"],
        "features": _records_from_frame(frame),
        "origins": metadata["origins"],
        "dataStatus": metadata["dataStatus"],
        "warnings": warnings,
    }
    if "units" in payload:
        normalized["units"] = {**(payload.get("units") or {}), TARGET_COLUMN: "%"}
    if "contractStatus" in payload:
        normalized["contractStatus"] = payload.get("contractStatus")
    if "requestedPeriod" in payload:
        normalized["requestedPeriod"] = payload.get("requestedPeriod")
    if "excludedSampleCount" in payload:
        normalized["excludedSampleCount"] = payload.get("excludedSampleCount")

    return AdaptedDataset(
        payload=normalized,
        frame=frame,
        metadata=metadata,
        source_format=source_format,
        resampled=resampled,
        warnings=warnings,
    )


def _is_name_value_unit(features: list[Any]) -> bool:
    sample = next((item for item in features if isinstance(item, dict)), None)
    if sample is None:
        return False
    return "name" in sample and "value" in sample and TARGET_COLUMN not in sample


def _is_temporal_record(features: list[Any]) -> bool:
    sample = next((item for item in features if isinstance(item, dict)), None)
    if sample is None:
        return False
    return TIMESTAMP_COLUMN in sample and TARGET_COLUMN in sample


def _from_temporal_records(features: list[Any], payload: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    units = payload.get("units") if isinstance(payload.get("units"), dict) else {}
    for index, item in enumerate(features):
        if not isinstance(item, dict):
            raise ValidationError(
                "Each temporal feature record must be an object",
                details={"code": "INVALID_INPUT", "index": index},
            )
        record = dict(item)
        if TIMESTAMP_COLUMN not in record:
            raise ValidationError(
                "Temporal record is missing timestamp",
                details={"code": "INVALID_INPUT", "index": index},
            )
        if TARGET_COLUMN not in record:
            raise ValidationError(
                "Temporal record is missing cpu_utilization",
                details={"code": "INVALID_INPUT", "index": index},
            )
        record[TARGET_COLUMN] = _maybe_scale_percent(
            TARGET_COLUMN,
            record.get(TARGET_COLUMN),
            units.get(TARGET_COLUMN) or record.get("unit"),
        )
        records.append(record)
    return records


def _from_name_value_unit(features: list[Any], payload: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    default_origin = _first_origin(payload)
    for index, item in enumerate(features):
        if not isinstance(item, dict):
            raise ValidationError(
                "Each name/value/unit feature must be an object",
                details={"code": "INVALID_INPUT", "index": index},
            )
        raw_name = item.get("name")
        if not raw_name:
            raise ValidationError(
                "name/value/unit feature is missing name",
                details={"code": "INVALID_INPUT", "index": index},
            )
        column = FEATURE_NAME_ALIASES.get(str(raw_name).strip().lower())
        if column is None:
            # Unknown metrics are ignored; they are not imputed.
            continue
        timestamp = item.get("timestamp") or _fallback_timestamp(payload)
        if timestamp is None:
            raise DatasetError(
                "name/value/unit features need a timestamp or period to build a window",
                details={"code": "INVALID_DATASET", "index": index},
            )
        key = str(timestamp)
        row = grouped.setdefault(
            key,
            {
                TIMESTAMP_COLUMN: timestamp,
                "origin": item.get("origin") or default_origin,
                "quality": item.get("quality") or "ok",
            },
        )
        row[column] = _maybe_scale_percent(column, item.get("value"), item.get("unit"))
        if item.get("origin"):
            row["origin"] = item.get("origin")
        if item.get("quality"):
            row["quality"] = item.get("quality")

    if not grouped:
        raise DatasetError(
            "name/value/unit payload did not contain a known computational-demand feature",
            details={"code": "INVALID_DATASET"},
        )
    return list(grouped.values())


def _normalize_frame(frame: pd.DataFrame, payload: dict[str, Any]) -> pd.DataFrame:
    result = frame.copy()
    result[TIMESTAMP_COLUMN] = pd.to_datetime(result[TIMESTAMP_COLUMN], errors="coerce", utc=True)
    if result[TIMESTAMP_COLUMN].isna().any():
        raise ValidationError(
            "Adapter found invalid timestamps",
            details={"code": "INVALID_INPUT", "invalid_count": int(result[TIMESTAMP_COLUMN].isna().sum())},
        )
    if "origin" not in result.columns:
        result["origin"] = _first_origin(payload)
    if "quality" not in result.columns:
        result["quality"] = "ok"
    result["origin"] = result["origin"].fillna(_first_origin(payload))
    result["quality"] = result["quality"].map(lambda value: QUALITY_ALIASES.get(str(value), value))
    result["quality"] = result["quality"].fillna("ok")

    # Both input formats already convert ratio values to percent before this step.
    result = result.sort_values(TIMESTAMP_COLUMN).reset_index(drop=True)
    return result


def _build_metadata(
    payload: dict[str, Any],
    frame: pd.DataFrame,
    warnings: list[str],
    *,
    strict: bool,
) -> dict[str, Any]:
    period = payload.get("period")
    if not isinstance(period, dict) or "start" not in period or "end" not in period:
        period = {
            "start": _iso(frame[TIMESTAMP_COLUMN].min()),
            "end": _iso(frame[TIMESTAMP_COLUMN].max()),
        }
    resource = payload.get("resource")
    if not isinstance(resource, dict) or not {"type", "cluster", "id"} <= set(resource):
        if strict:
            raise ValidationError(
                "Dataset metadata missing required resource fields",
                details={"code": "INVALID_INPUT"},
            )
        resource = {
            "type": "node",
            "cluster": "unknown",
            "id": "unknown",
        }
    origins = payload.get("origins")
    if not isinstance(origins, list) or not origins:
        origins = sorted({str(item) for item in frame["origin"].dropna().unique()}) or ["unknown"]
    invalid_origins = [item for item in origins if item not in ALLOWED_ORIGINS]
    if invalid_origins:
        raise ValidationError(
            f"Invalid dataset origins: {invalid_origins}",
            details={"code": "INVALID_INPUT", "allowed": sorted(ALLOWED_ORIGINS)},
        )
    data_status = payload.get("dataStatus") or ("partial" if warnings else "complete")
    if data_status == "incomplete":
        data_status = "partial"
    return {
        "schemaVersion": payload.get("schemaVersion", SCHEMA_VERSION),
        "datasetId": payload.get("datasetId") or "dataset-unknown",
        "period": period,
        "resource": resource,
        "origins": origins,
        "dataStatus": data_status,
        "warnings": warnings,
    }


def _records_from_frame(frame: pd.DataFrame) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in frame.to_dict(orient="records"):
        item = dict(row)
        if TIMESTAMP_COLUMN in item:
            item[TIMESTAMP_COLUMN] = _iso(item[TIMESTAMP_COLUMN])
        records.append(item)
    return records


def _maybe_scale_percent(column: str, value: Any, unit: Any) -> Any:
    if value is None:
        return None
    if not isinstance(value, (int, float)):
        return value
    unit_text = str(unit).strip().lower() if unit is not None else ""
    if column in PERCENT_COLUMNS and unit_text in RATIO_UNITS:
        return float(value) * 100.0
    return value


def _first_origin(payload: dict[str, Any]) -> str:
    origins = payload.get("origins")
    if isinstance(origins, list) and origins:
        return str(origins[0])
    return "unknown"


def _fallback_timestamp(payload: dict[str, Any]) -> str | None:
    period = payload.get("period")
    if isinstance(period, dict):
        return period.get("end") or period.get("start")
    requested = payload.get("requestedPeriod")
    if isinstance(requested, dict):
        return requested.get("end") or requested.get("start")
    return None


def _iso(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC").isoformat().replace("+00:00", "Z")
