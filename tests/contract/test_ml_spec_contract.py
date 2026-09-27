from __future__ import annotations

from src.adapters.input_adapter import adapt_input


def test_ml_spec_name_value_unit_contract(name_value_unit_payload):
    assert name_value_unit_payload["schemaVersion"] == "1.0"
    first = name_value_unit_payload["features"][0]
    assert {"name", "value", "unit"} <= set(first)
    adapted = adapt_input(name_value_unit_payload, expected_frequency="5m")
    assert adapted.source_format == "name_value_unit"
    assert "cpu_utilization" in adapted.frame.columns
