from __future__ import annotations

from src.adapters.input_adapter import adapt_input


REQUIRED_ROOT = {
    "schemaVersion",
    "datasetId",
    "period",
    "resource",
    "features",
    "origins",
    "dataStatus",
}


def test_dataprocessing_contract_fields_are_accepted(dataprocessing_payload):
    assert REQUIRED_ROOT <= set(dataprocessing_payload)
    assert dataprocessing_payload["contractStatus"] == "provisional"
    assert dataprocessing_payload["units"]["cpu_utilization"] == "%"
    assert dataprocessing_payload["dataStatus"] in {"complete", "partial", "no_data"}
    first = dataprocessing_payload["features"][0]
    assert {"timestamp", "cpu_utilization", "origin", "quality"} <= set(first)
    assert first["origin"] == "simulated"

    adapted = adapt_input(dataprocessing_payload, expected_frequency="5m")
    assert adapted.metadata["schemaVersion"] == "1.0"
    assert adapted.payload["dataStatus"] in {"complete", "partial"}
    assert adapted.frame["cpu_utilization"].between(0, 100).all()


def test_dataprocessing_extra_fields_do_not_break_adapter(dataprocessing_payload):
    adapted = adapt_input(dataprocessing_payload, expected_frequency="5m")
    assert adapted.payload.get("contractStatus") == "provisional"
    assert "requestedPeriod" in adapted.payload
    assert "excludedSampleCount" in adapted.payload
