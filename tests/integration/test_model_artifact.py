from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd
import pytest
import yaml

from src.data.generate import write_simulated_dataset
from src.inference.predict import load_selected_model, predict
from src.training.train import run_pipeline


def test_selected_artifact_can_be_reloaded_and_used(tmp_path, config):
    dataset_path = tmp_path / "dataset.json"
    write_simulated_dataset(dataset_path, days=1, frequency_minutes=5, seed=3, dataset_id="dataset-art-001")
    cfg = json.loads(json.dumps(config))
    cfg["random_forest"]["n_estimators"] = 12
    cfg["xgboost"]["n_estimators"] = 12
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

    summary = run_pipeline(config_path=config_path, dataset_path=dataset_path, skip_mlflow=True)
    selected_dir = tmp_path / "models" / "selected"

    loaded = load_selected_model(selected_dir)
    assert "model" in loaded["bundle"]
    assert loaded["metadata"]["datasetId"] == "dataset-art-001"
    assert Path(loaded["path"]).exists()

    sample = pd.read_csv(tmp_path / "results" / "predictions" / "test_predictions.csv")
    features = loaded["bundle"]["features"]
    # Rebuild one inference row from the selected model's stored test matrix is not
    # available here; use the in-memory test features from a second predict on
    # current CPU-only persistence-compatible columns if needed.
    bundle = joblib.load(selected_dir / "model.joblib")
    model = bundle["model"]
    # Use a row constructed with required feature names from metadata defaults.
    row = {name: 0.0 for name in features}
    if "cpu_utilization" in row:
        row["cpu_utilization"] = 41.5
    if "hour" in row:
        row["hour"] = 10
    if "minute" in row:
        row["minute"] = 15
    if "day_of_week" in row:
        row["day_of_week"] = 1
    if "day_of_month" in row:
        row["day_of_month"] = 1
    result = predict(row, model_dir=selected_dir)
    assert result["origin"] == "estimated"
    assert result["unit"] == "%"
    assert result["target"] == "cpu_utilization"
    assert result["modelVersion"] == summary["selected"].get("model") or result["modelVersion"] == loaded["metadata"]["modelVersion"]
    assert isinstance(result["value"], float)
    assert result["latency_ms"] >= 0
    _ = model
    _ = sample
