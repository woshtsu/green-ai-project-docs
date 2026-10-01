"""Offline inference. Does not query infrastructure."""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from src.adapters.input_adapter import adapt_input
from src.adapters.output_adapter import adapt_output
from src.config.settings import PROJECT_ROOT, load_config, resolve_path
from src.data.schema import EXPECTED_FREQUENCY, TARGET_UNIT
from src.exceptions import ArtifactIntegrityError, ModelNotFoundError, ValidationError
from src.preprocessing.cleaning import clean_dataset
from src.preprocessing.features import assert_no_future_features, build_supervised_frame
from src.reproducibility import sha256_file


def load_selected_model(model_dir: str | Path | None = None) -> dict[str, Any]:
    directory = Path(model_dir) if model_dir else resolve_path(load_config()["paths"]["models_selected"])
    model_path = directory / "model.joblib"
    metadata_path = directory / "metadata.json"
    if not model_path.exists():
        raise ModelNotFoundError(f"Serialized model not found: {model_path}")
    metadata = {}
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        expected = metadata.get("modelSha256")
        if expected:
            actual = sha256_file(model_path)
            if actual != expected:
                raise ArtifactIntegrityError(
                    "model.joblib hash does not match metadata.modelSha256",
                    details={"expected": expected, "actual": actual},
                )
    bundle = joblib.load(model_path)
    return {"bundle": bundle, "metadata": metadata, "path": model_path}


def predict(
    features: pd.DataFrame | dict[str, Any] | list[dict[str, Any]],
    model_dir: str | Path | None = None,
    resource: dict[str, Any] | None = None,
    predicted_for: str | None = None,
) -> dict[str, Any]:
    """Run inference on already-engineered features."""
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
    if values.size == 0 or not np.isfinite(values).all():
        raise ValidationError("Inference produced empty or non-finite predictions")

    generated_at = datetime.now(timezone.utc).isoformat()
    first = float(values[0])
    return {
        "predictionId": f"pred-{uuid.uuid4()}",
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
        "generatedAt": generated_at,
    }


def predict_from_window(
    records: pd.DataFrame | list[dict[str, Any]] | dict[str, Any],
    model_dir: str | Path | None = None,
    config: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Apply the training preprocessor to a raw temporal window, then predict."""
    cfg = config or load_config()
    loaded = load_selected_model(model_dir)
    metadata = loaded["metadata"]
    horizon = str(metadata.get("horizon") or cfg.get("default_horizon", "15m"))
    expected_frequency = _model_frequency(metadata, cfg)
    frame, adapted_meta = _window_frame(records, expected_frequency)
    cleaned = clean_dataset(frame)
    supervised, feature_names, _frequency, _steps = build_supervised_frame(
        cleaned,
        cfg,
        horizon,
        require_target=False,
    )
    if supervised.empty:
        raise ValidationError("Window did not produce a complete supervised row")
    last = supervised.iloc[[-1]]
    result = predict(
        last[feature_names],
        model_dir=model_dir,
        resource=_resolve_resource(adapted_meta, metadata),
    )
    predicted_for = pd.Timestamp(last["target_timestamp"].iloc[0]).isoformat()
    result["predictedFor"] = predicted_for
    result["horizon"] = horizon
    result["requestId"] = request_id
    result["warnings"] = list(adapted_meta.get("warnings", []))
    if adapted_meta.get("datasetId"):
        result["inputDatasetId"] = adapted_meta.get("datasetId")
    result["inputWindow"] = {
        "records": int(len(frame)),
        "supervised_rows": int(len(supervised)),
        "prediction_time": pd.Timestamp(last["prediction_time"].iloc[0]).isoformat(),
    }
    return result


def predict_from_payload(
    payload: dict[str, Any],
    model_dir: str | Path | None = None,
    config: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Public inference path: adapt contract → features → model → output contract."""
    result = predict_from_window(payload, model_dir=model_dir, config=config, request_id=request_id)
    return adapt_output(
        result,
        resource=result.get("resource"),
        dataset_id=payload.get("datasetId") or result.get("inputDatasetId"),
    )


def _window_frame(
    records: pd.DataFrame | list[dict[str, Any]] | dict[str, Any],
    expected_frequency: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if isinstance(records, pd.DataFrame):
        return records.copy(), {}
    if isinstance(records, dict):
        adapted = adapt_input(records, strict=False, expected_frequency=expected_frequency)
        return adapted.frame, adapted.metadata
    if isinstance(records, list):
        adapted = adapt_input(
            {"schemaVersion": "1.0", "features": records},
            strict=False,
            expected_frequency=expected_frequency,
        )
        return adapted.frame, adapted.metadata
    raise ValidationError("Unsupported feature payload")


def _resolve_resource(adapted_meta: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any] | None:
    adapted = adapted_meta.get("resource") if isinstance(adapted_meta.get("resource"), dict) else {}
    if adapted.get("id") and adapted.get("id") != "unknown":
        return adapted
    stored = metadata.get("resource") if isinstance(metadata.get("resource"), dict) else None
    return stored or adapted or None


def _model_frequency(metadata: dict[str, Any], config: dict[str, Any]) -> str:
    raw = metadata.get("frequency")
    if isinstance(raw, str) and raw.endswith(("s", "m", "h")):
        try:
            delta = pd.Timedelta(raw)
            minutes = int(delta.total_seconds() // 60)
            if minutes >= 1:
                return f"{minutes}m"
        except Exception:
            pass
    dataset_minutes = config.get("dataset", {}).get("frequency_minutes")
    if dataset_minutes:
        return f"{int(dataset_minutes)}m"
    return EXPECTED_FREQUENCY


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
