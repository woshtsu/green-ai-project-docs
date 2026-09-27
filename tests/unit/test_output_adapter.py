from src.adapters.output_adapter import adapt_output


def test_output_origin_is_always_estimated():
    result = adapt_output(
        {
            "predictionId": "pred-1",
            "value": 41.2,
            "unit": "%",
            "target": "cpu_utilization",
            "predictedFor": "2026-09-01T00:15:00+00:00",
            "generatedAt": "2026-09-01T00:00:01+00:00",
            "modelVersion": "1.0.0",
            "horizon": "15m",
            "origin": "observed",
            "inputDatasetId": "dataset-1",
        },
        resource={"type": "node", "cluster": "c", "id": "n"},
        dataset_id="dataset-1",
    )
    assert result["origin"] == "estimated"
    assert result["target"] == "cpu_utilization"
    assert result["unit"] == "%"
    assert result["resource"]["id"] == "n"
    assert result["inputDatasetId"] == "dataset-1"
    assert result["value"] == 41.2
