from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from src.data.generate import generate_dataprocessing_dataset, write_simulated_dataset
from src.exceptions import ModelNotFoundError
from src.service.app import app
from src.training.train import run_pipeline


def _train(tmp_path: Path, config: dict) -> Path:
    dataset_path = tmp_path / "dataset.json"
    write_simulated_dataset(dataset_path, days=1, frequency_minutes=5, seed=11, dataset_id="dataset-api-001")
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


def test_health_reports_model_state(tmp_path, config, monkeypatch):
    selected = _train(tmp_path, config)
    monkeypatch.setenv("ML_MODEL_DIR", str(selected))
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["modelLoaded"] is True
    assert body["modelVersion"]


def test_health_without_model(monkeypatch):
    def _missing():
        raise ModelNotFoundError("missing")

    monkeypatch.setattr("src.service.app.load_selected_model", _missing)
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["modelLoaded"] is False


def test_predict_from_fixture_window(tmp_path, config, compact_payload, monkeypatch):
    selected = _train(tmp_path, config)
    monkeypatch.setenv("ML_MODEL_DIR", str(selected))
    client = TestClient(app)
    response = client.post("/predict", json=compact_payload)
    assert response.status_code == 200
    body = response.json()
    assert body["origin"] == "estimated"
    assert body["target"] == "cpu_utilization"
    assert body["unit"] == "%"
    assert body["predictionId"]
    assert body["predictedFor"]
    assert body["inputDatasetId"] == compact_payload["datasetId"]
    assert isinstance(body["value"], float)


def test_predict_rejects_invalid_schema():
    client = TestClient(app)
    response = client.post(
        "/v1/predictions",
        json={
            "schemaVersion": "9.0",
            "features": [
                {"timestamp": "2026-09-01T00:00:00Z", "cpu_utilization": 10, "origin": "simulated", "quality": "ok"},
                {"timestamp": "2026-09-01T00:05:00Z", "cpu_utilization": 11, "origin": "simulated", "quality": "ok"},
            ],
        },
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_INPUT"


def test_predict_rejects_empty_dataset():
    client = TestClient(app)
    response = client.post("/predict", json={"schemaVersion": "1.0", "features": []})
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_DATASET"


def test_predict_rejects_no_data(no_data_payload):
    client = TestClient(app)
    response = client.post("/predict", json=no_data_payload)
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_DATASET"


def test_predict_rejects_partial_window_too_short():
    client = TestClient(app)
    response = client.post(
        "/predict",
        json={
            "schemaVersion": "1.0",
            "datasetId": "tiny",
            "features": [
                {"timestamp": "2026-09-01T00:00:00Z", "cpu_utilization": 10, "origin": "simulated", "quality": "ok"},
                {"timestamp": "2026-09-01T00:05:00Z", "cpu_utilization": 11, "origin": "simulated", "quality": "ok"},
            ],
        },
    )
    assert response.status_code in {400, 422}


def test_predict_model_unavailable(tmp_path, monkeypatch):
    monkeypatch.setenv("ML_MODEL_DIR", str(tmp_path / "missing-model"))
    client = TestClient(app)
    response = client.post(
        "/predict",
        json={
            "schemaVersion": "1.0",
            "features": generate_dataprocessing_dataset(hours=4)["features"][:40],
        },
    )
    assert response.status_code == 503
    assert response.json()["code"] == "MODEL_UNAVAILABLE"
