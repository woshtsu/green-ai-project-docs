from __future__ import annotations

import pandas as pd
import pytest

from src.data.validation import validate_dataset
from src.exceptions import InsufficientDataError, ValidationError


def _meta(origins=None, status="complete") -> dict:
    return {
        "schemaVersion": "1.0",
        "datasetId": "dataset-test-001",
        "period": {"start": "2026-09-01T00:00:00Z", "end": "2026-09-01T01:00:00Z"},
        "resource": {"type": "node", "cluster": "cluster-01", "id": "node-01"},
        "features": [],
        "origins": origins or ["simulated"],
        "dataStatus": status,
        "warnings": [],
    }


def _frame(rows) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    return frame


def test_valid_dataset_passes(sample_frame, sample_payload):
    report = validate_dataset(sample_frame, sample_payload)
    assert report["valid"] is True
    assert report["records"] == len(sample_frame)
    assert report["frequency_seconds"] == 300


def test_empty_dataset_is_insufficient():
    with pytest.raises(InsufficientDataError) as exc:
        validate_dataset(pd.DataFrame(), _meta())
    assert exc.value.code == "INSUFFICIENT_DATA"
    assert exc.value.details["available_records"] == 0


def test_invalid_timestamp_is_rejected():
    frame = pd.DataFrame(
        [
            {"timestamp": "2026-09-01T00:00:00Z", "cpu_utilization": 10, "origin": "simulated", "quality": "ok"},
            {"timestamp": "not-a-date", "cpu_utilization": 11, "origin": "simulated", "quality": "ok"},
        ]
    )
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    with pytest.raises(ValidationError, match="Invalid timestamps"):
        validate_dataset(frame, _meta())


def test_missing_columns_are_rejected():
    frame = pd.DataFrame({"timestamp": pd.to_datetime(["2026-09-01T00:00:00Z"], utc=True)})
    with pytest.raises(ValidationError, match="Missing required columns"):
        validate_dataset(frame, _meta())


def test_nan_target_is_rejected():
    frame = _frame(
        [
            {"timestamp": "2026-09-01T00:00:00Z", "cpu_utilization": None, "origin": "simulated", "quality": "ok"},
        ]
    )
    with pytest.raises(ValidationError, match="Missing values"):
        validate_dataset(frame, _meta())


def test_inf_is_rejected():
    frame = _frame(
        [
            {"timestamp": "2026-09-01T00:00:00Z", "cpu_utilization": float("inf"), "origin": "simulated", "quality": "ok"},
        ]
    )
    with pytest.raises(ValidationError, match="Infinite"):
        validate_dataset(frame, _meta())


def test_duplicates_are_rejected():
    frame = _frame(
        [
            {"timestamp": "2026-09-01T00:00:00Z", "cpu_utilization": 10, "origin": "simulated", "quality": "ok"},
            {"timestamp": "2026-09-01T00:00:00Z", "cpu_utilization": 11, "origin": "simulated", "quality": "ok"},
        ]
    )
    with pytest.raises(ValidationError, match="Duplicate"):
        validate_dataset(frame, _meta())


def test_invalid_origin_is_rejected():
    frame = _frame(
        [
            {"timestamp": "2026-09-01T00:00:00Z", "cpu_utilization": 10, "origin": "synthetic", "quality": "ok"},
        ]
    )
    with pytest.raises(ValidationError, match="Invalid origin"):
        validate_dataset(frame, _meta())


def test_invalid_quality_is_rejected():
    frame = _frame(
        [
            {"timestamp": "2026-09-01T00:00:00Z", "cpu_utilization": 10, "origin": "simulated", "quality": "bad"},
        ]
    )
    with pytest.raises(ValidationError, match="Invalid quality"):
        validate_dataset(frame, _meta())


def test_timestamp_without_timezone_is_rejected():
    frame = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2026-09-01T00:00:00", "2026-09-01T00:05:00"]),
            "cpu_utilization": [10.0, 11.0],
            "origin": ["simulated", "simulated"],
            "quality": ["ok", "ok"],
        }
    )
    with pytest.raises(ValidationError, match="timezone"):
        validate_dataset(frame, _meta())


def test_invalid_data_status_is_rejected():
    frame = _frame(
        [
            {"timestamp": "2026-09-01T00:00:00Z", "cpu_utilization": 10, "origin": "simulated", "quality": "ok"},
        ]
    )
    with pytest.raises(ValidationError, match="Invalid dataStatus"):
        validate_dataset(frame, _meta(status="broken"))
