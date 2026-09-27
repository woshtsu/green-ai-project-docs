from __future__ import annotations

import pandas as pd
import pytest

from src.adapters.input_adapter import adapt_input
from src.exceptions import DatasetError, ValidationError


def test_temporal_dataprocessing_payload_is_adapted(dataprocessing_payload):
    adapted = adapt_input(dataprocessing_payload, expected_frequency="5m")
    assert adapted.source_format == "temporal_records"
    assert adapted.resampled is True
    assert not adapted.frame.empty
    assert adapted.frame["timestamp"].dt.tz is not None
    assert adapted.metadata["datasetId"] == dataprocessing_payload["datasetId"]
    assert adapted.metadata["resource"]["id"] == "fixture-node-01"
    diffs = adapted.frame["timestamp"].sort_values().diff().dropna()
    assert diffs.median() == pd.Timedelta(minutes=5)
    assert not (adapted.frame["cpu_utilization"] == 0).all()


def test_name_value_unit_payload_is_pivoted(name_value_unit_payload):
    adapted = adapt_input(name_value_unit_payload, expected_frequency="5m")
    assert adapted.source_format == "name_value_unit"
    assert "cpu_utilization" in adapted.frame.columns
    assert adapted.frame["cpu_utilization"].notna().all()


def test_ratio_cpu_is_converted_to_percent():
    payload = {
        "schemaVersion": "1.0",
        "datasetId": "dataset-ratio",
        "period": {"start": "2026-09-01T00:00:00Z", "end": "2026-09-01T00:05:00Z"},
        "resource": {"type": "node", "cluster": "c", "id": "n"},
        "origins": ["simulated"],
        "dataStatus": "complete",
        "features": [
            {
                "name": "node.cpu.utilization",
                "value": 0.41,
                "unit": "ratio",
                "timestamp": "2026-09-01T00:00:00Z",
                "origin": "simulated",
                "quality": "valid",
            },
            {
                "name": "node.cpu.utilization",
                "value": 0.44,
                "unit": "ratio",
                "timestamp": "2026-09-01T00:05:00Z",
                "origin": "simulated",
                "quality": "ok",
            },
        ],
    }
    adapted = adapt_input(payload, expected_frequency="5m")
    assert adapted.frame.loc[0, "cpu_utilization"] == pytest.approx(41.0)
    assert adapted.frame.loc[0, "quality"] == "ok"


def test_no_data_is_rejected_and_not_converted_to_zero(no_data_payload):
    with pytest.raises(DatasetError, match="no usable observations"):
        adapt_input(no_data_payload)


def test_empty_features_are_rejected():
    with pytest.raises(DatasetError):
        adapt_input({"schemaVersion": "1.0", "features": []})


def test_unknown_schema_is_rejected():
    with pytest.raises(ValidationError, match="Unsupported schemaVersion"):
        adapt_input({"schemaVersion": "9.0", "features": [{"timestamp": "2026-09-01T00:00:00Z", "cpu_utilization": 10}]})


def test_resample_does_not_fill_empty_bins_with_zero():
    payload = {
        "schemaVersion": "1.0",
        "features": [
            {"timestamp": "2026-09-01T00:00:00Z", "cpu_utilization": 10, "origin": "simulated", "quality": "ok"},
            {"timestamp": "2026-09-01T00:00:15Z", "cpu_utilization": 12, "origin": "simulated", "quality": "ok"},
            {"timestamp": "2026-09-01T00:20:00Z", "cpu_utilization": 30, "origin": "simulated", "quality": "ok"},
            {"timestamp": "2026-09-01T00:20:15Z", "cpu_utilization": 32, "origin": "simulated", "quality": "ok"},
        ],
    }
    adapted = adapt_input(payload, expected_frequency="5m")
    assert adapted.resampled is True
    assert len(adapted.frame) == 2
    assert 0.0 not in set(adapted.frame["cpu_utilization"].tolist())
