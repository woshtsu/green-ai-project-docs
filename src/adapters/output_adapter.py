"""Map internal inference results to the public prediction contract."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from src.data.schema import TARGET_COLUMN, TARGET_UNIT


def adapt_output(
    result: dict[str, Any],
    *,
    resource: dict[str, Any] | None = None,
    dataset_id: str | None = None,
) -> dict[str, Any]:
    """Build the external prediction payload. origin is always estimated."""
    resolved_resource = resource or result.get("resource") or {
        "type": "node",
        "cluster": "unknown",
        "id": "unknown",
    }
    generated_at = result.get("generatedAt") or datetime.now(timezone.utc).isoformat()
    return {
        "predictionId": result.get("predictionId") or f"pred-{uuid4()}",
        "resource": {
            "type": resolved_resource.get("type", "node"),
            "cluster": resolved_resource.get("cluster", "unknown"),
            "id": resolved_resource.get("id", "unknown"),
        },
        "target": result.get("target") or TARGET_COLUMN,
        "predictedFor": result.get("predictedFor"),
        "value": float(result["value"]),
        "unit": result.get("unit") or TARGET_UNIT,
        "modelVersion": result.get("modelVersion"),
        "inputDatasetId": dataset_id or result.get("inputDatasetId"),
        "origin": "estimated",
        "generatedAt": generated_at,
        "horizon": result.get("horizon"),
    }
