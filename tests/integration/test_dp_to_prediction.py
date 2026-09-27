from __future__ import annotations

import json
from pathlib import Path

import yaml

from src.adapters.input_adapter import adapt_input
from src.adapters.output_adapter import adapt_output
from src.data.generate import write_simulated_dataset
from src.inference.predict import predict_from_payload, predict_from_window
from src.preprocessing.cleaning import clean_dataset
from src.preprocessing.features import build_supervised_frame
from src.training.train import run_pipeline


def _train(tmp_path: Path, config: dict) -> Path:
    dataset_path = tmp_path / "dataset.json"
    write_simulated_dataset(dataset_path, days=1, frequency_minutes=5, seed=21, dataset_id="dataset-int-001")
    cfg = json.loads(json.dumps(config))
    cfg["random_forest"]["n_estimators"] = 8
    cfg["xgboost"]["n_estimators"] = 8
    cfg["latency_repeats"] = 1
    cfg["horizons"] = ["15m"]
    cfg["paths"] = {
        "raw_data": str(dataset_path),
        "interim_dir": str(tmp_path / "interim"),
        "processed_dir": str(tmp_path / "processed"),
        "models_candidate": str(tmp_path / "models" / "candidate"),
        "models_selected": str(tmp_path / "models" / "selected"),
        "results_dir": str(tmp_path / "results"),
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    run_pipeline(config_path=config_path, dataset_path=dataset_path, skip_mlflow=True)
    return tmp_path / "models" / "selected"


def test_dataprocessing_json_to_prediction_response(tmp_path, config, dataprocessing_payload):
    selected = _train(tmp_path, config)
    adapted = adapt_input(dataprocessing_payload, expected_frequency="5m")
    cleaned = clean_dataset(adapted.frame)
    supervised, features, _frequency, _steps = build_supervised_frame(
        cleaned,
        config,
        "15m",
        require_target=False,
    )
    assert not supervised.empty
    assert "target" not in features

    result = predict_from_window(dataprocessing_payload, model_dir=selected, config=config)
    response = adapt_output(result, resource=adapted.metadata["resource"], dataset_id=adapted.metadata["datasetId"])
    assert response["origin"] == "estimated"
    assert response["target"] == "cpu_utilization"
    assert response["resource"]["id"] == "fixture-node-01"
    assert response["inputDatasetId"] == dataprocessing_payload["datasetId"]
    assert response["predictedFor"]
    assert isinstance(response["value"], float)


def test_predict_from_payload_uses_output_contract(tmp_path, config, dataprocessing_payload):
    selected = _train(tmp_path, config)
    response = predict_from_payload(dataprocessing_payload, model_dir=selected, config=config)
    assert set(response) >= {
        "predictionId",
        "resource",
        "target",
        "predictedFor",
        "value",
        "unit",
        "modelVersion",
        "inputDatasetId",
        "origin",
        "generatedAt",
    }
    assert response["origin"] == "estimated"
