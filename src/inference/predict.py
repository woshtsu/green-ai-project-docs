"""Offline inference. Does not query infrastructure."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from src.config.settings import PROJECT_ROOT, load_config, resolve_path
from src.data.schema import TARGET_UNIT
from src.exceptions import ModelNotFoundError, ValidationError
from src.preprocessing.features import assert_no_future_features


def load_selected_model(model_dir: str | Path | None = None) -> dict[str, Any]:
    directory = Path(model_dir) if model_dir else resolve_path(load_config()["paths"]["models_selected"])
    model_path = directory / "model.joblib"
    metadata_path = directory / "metadata.json"
    if not model_path.exists():
        raise ModelNotFoundError(f"Serialized model not found: {model_path}")
    bundle = joblib.load(model_path)
    metadata = {}
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    return {"bundle": bundle, "metadata": metadata, "path": model_path}


def predict(
    features: pd.DataFrame | dict[str, Any] | list[dict[str, Any]],
    model_dir: str | Path | None = None,
    resource: dict[str, Any] | None = None,
    predicted_for: str | None = None,
) -> dict[str, Any]:
    """Run inference and return Prediction-Service-ready metadata."""
    loaded = load_selected_model(model_dir)
    bundle = loaded["bundle"]
    metadata = loaded["metadata"]
    model = bundle["model"]
    feature_names: list[str] = list(bundle["features"])
    assert_no_future_features(feature_names)

    frame = _as_frame(features)
    missing = [name for name in feature_names if name not in frame.columns]
    if missing:
        raise ValidationError(f"Missing inference features: {missing}", details={"missing": missing})
    extra_future = [name for name in frame.columns if name not in feature_names]
    assert_no_future_features(extra_future)

    ordered = frame[feature_names]
    started = time.perf_counter()
    values = np.asarray(model.predict(ordered), dtype=float)
    latency_ms = (time.perf_counter() - started) * 1000.0
    if values.size == 0 or np.isnan(values).any():
        raise ValidationError("Inference produced empty or NaN predictions")

    first = float(values[0])
    payload = {
        "value": first,
        "values": values.tolist(),
        "unit": metadata.get("unit", TARGET_UNIT),
        "target": metadata.get("target", "cpu_utilization"),
        "horizon": metadata.get("horizon"),
        "modelVersion": metadata.get("modelVersion"),
        "modelType": metadata.get("modelType"),
        "origin": "estimated",
        "inputDatasetId": metadata.get("datasetId"),
        "latency_ms": latency_ms,
        "features_used": feature_names,
        "resource": resource or metadata.get("resource"),
        "predictedFor": predicted_for,
    }
    return payload


def _as_frame(features: pd.DataFrame | dict[str, Any] | list[dict[str, Any]]) -> pd.DataFrame:
    if isinstance(features, pd.DataFrame):
        return features.copy()
    if isinstance(features, dict):
        return pd.DataFrame([features])
    if isinstance(features, list):
        return pd.DataFrame(features)
    raise ValidationError("Unsupported feature payload")


def selected_model_dir(config: dict[str, Any] | None = None) -> Path:
    cfg = config or load_config()
    path = resolve_path(cfg["paths"]["models_selected"])
    if not path.is_absolute():
        return PROJECT_ROOT / path
    return path
