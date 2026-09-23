from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from src.data.generate import write_simulated_dataset
from src.exceptions import InsufficientDataError
from src.training.train import run_pipeline


def _write_config(tmp_path: Path, base: dict, dataset_path: Path) -> Path:
    cfg = json.loads(json.dumps(base))
    cfg["random_forest"]["n_estimators"] = 15
    cfg["xgboost"]["n_estimators"] = 15
    cfg["latency_repeats"] = 2
    cfg["mlflow"]["tracking_uri"] = str(tmp_path / "mlruns")
    cfg["paths"] = {
        "raw_data": str(dataset_path),
        "interim_dir": str(tmp_path / "interim"),
        "processed_dir": str(tmp_path / "processed"),
        "models_candidate": str(tmp_path / "models" / "candidate"),
        "models_selected": str(tmp_path / "models" / "selected"),
        "results_dir": str(tmp_path / "results"),
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return path


def test_full_training_pipeline(tmp_path, config):
    dataset_path = tmp_path / "dataset.json"
    write_simulated_dataset(dataset_path, days=1, frequency_minutes=5, seed=42, dataset_id="dataset-it-001")
    config_path = _write_config(tmp_path, config, dataset_path)

    summary = run_pipeline(config_path=config_path, dataset_path=dataset_path, skip_mlflow=False)

    assert summary["dataset_id"] == "dataset-it-001"
    assert summary["data_kind"] == "technical_simulated"
    assert summary["selected"]["model"] in {"persistence", "moving_average", "random_forest", "xgboost"}
    assert summary["selected"]["horizon"] == "15m"
    models = {row["model"] for row in summary["comparison"]}
    horizons = {row["horizon"] for row in summary["comparison"]}
    assert {"persistence", "moving_average", "random_forest", "xgboost"} <= models
    assert {"5m", "15m", "30m"} <= horizons

    selected_dir = tmp_path / "models" / "selected"
    assert (selected_dir / "model.joblib").exists()
    assert (selected_dir / "metadata.json").exists()
    assert (tmp_path / "results" / "metrics" / "model_comparison.csv").exists()
    assert (tmp_path / "results" / "reports" / "model_report.md").exists()

    metadata = json.loads((selected_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["target"] == "cpu_utilization"
    assert metadata["unit"] == "%"
    assert metadata["dataKind"] == "simulated"
    assert metadata["origins"] == ["simulated"]


def test_insufficient_data_is_explicit(tmp_path, config):
    dataset_path = tmp_path / "tiny.json"
    write_simulated_dataset(dataset_path, days=1, frequency_minutes=5, seed=1, dataset_id="dataset-tiny")
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    payload["features"] = payload["features"][:8]
    payload["period"]["end"] = payload["features"][-1]["timestamp"]
    dataset_path.write_text(json.dumps(payload), encoding="utf-8")
    config_path = _write_config(tmp_path, config, dataset_path)

    with pytest.raises(InsufficientDataError) as exc:
        run_pipeline(config_path=config_path, dataset_path=dataset_path, skip_mlflow=True)
    assert exc.value.code == "INSUFFICIENT_DATA"
    assert "available_records" in exc.value.details
    assert "horizon" in exc.value.details
    assert "reason" in exc.value.details


def test_pipeline_is_reproducible(tmp_path, config):
    dataset_path = tmp_path / "dataset.json"
    write_simulated_dataset(dataset_path, days=1, frequency_minutes=5, seed=42)
    first_dir = tmp_path / "run1"
    second_dir = tmp_path / "run2"
    first_dir.mkdir()
    second_dir.mkdir()
    first_cfg = _write_config(first_dir, config, dataset_path)
    second_cfg = _write_config(second_dir, config, dataset_path)

    first = run_pipeline(config_path=first_cfg, dataset_path=dataset_path, skip_mlflow=True)
    second = run_pipeline(config_path=second_cfg, dataset_path=dataset_path, skip_mlflow=True)

    assert first["selected"]["model"] == second["selected"]["model"]
    assert first["selected"]["mae"] == pytest.approx(second["selected"]["mae"])
    assert first["selected"]["rmse"] == pytest.approx(second["selected"]["rmse"])
    assert first["selected"]["smape"] == pytest.approx(second["selected"]["smape"])

    pred_a = pd.read_csv(first_dir / "results" / "predictions" / "selected_model_predictions.csv")
    pred_b = pd.read_csv(second_dir / "results" / "predictions" / "selected_model_predictions.csv")
    pd.testing.assert_series_equal(pred_a["y_pred"], pred_b["y_pred"], check_names=False)
