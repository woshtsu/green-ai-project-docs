"""Internal Prediction API.

Does not query Prometheus, Supabase or Kubernetes.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from src.exceptions import (
    ArtifactIntegrityError,
    DatasetError,
    InsufficientDataError,
    LeakageError,
    MLError,
    ModelNotFoundError,
    ValidationError,
)
from src.inference.predict import load_selected_model, predict_from_payload

LOGGER = logging.getLogger(__name__)

app = FastAPI(
    title="Prediction Service",
    version="1.0.0",
    description="Internal API for short-term computational demand estimates.",
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response


def _error_payload(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"code": code, "message": message, "details": details or {}}


def _map_error(exc: Exception) -> tuple[int, str, str, dict[str, Any]]:
    if isinstance(exc, (ModelNotFoundError, ArtifactIntegrityError)):
        return 503, "MODEL_UNAVAILABLE", exc.message, getattr(exc, "details", {}) or {}
    if isinstance(exc, (DatasetError, InsufficientDataError)):
        return 422, "INVALID_DATASET", exc.message, getattr(exc, "details", {}) or {}
    if isinstance(exc, (ValidationError, LeakageError)):
        return 400, "INVALID_INPUT", exc.message, getattr(exc, "details", {}) or {}
    if isinstance(exc, MLError):
        return 400, exc.code, exc.message, exc.details
    return 500, "INFERENCE_ERROR", "Inference failed", {}


@app.exception_handler(MLError)
async def ml_error_handler(request: Request, exc: MLError) -> JSONResponse:
    status, code, message, details = _map_error(exc)
    return JSONResponse(
        status_code=status,
        content=_error_payload(code, message, details),
        headers={"X-Request-Id": getattr(request.state, "request_id", "")},
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    LOGGER.exception("Unhandled inference error")
    return JSONResponse(
        status_code=500,
        content=_error_payload("INFERENCE_ERROR", "Inference failed"),
        headers={"X-Request-Id": getattr(request.state, "request_id", "")},
    )


@app.get("/health")
def health() -> dict[str, Any]:
    try:
        loaded = load_selected_model()
        metadata = loaded["metadata"]
        return {
            "status": "ok",
            "modelLoaded": True,
            "modelVersion": metadata.get("modelVersion"),
        }
    except MLError:
        return {
            "status": "degraded",
            "modelLoaded": False,
            "modelVersion": None,
        }


@app.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "live"}


@app.get("/health/ready")
def readiness() -> dict[str, Any]:
    loaded = load_selected_model()
    metadata = loaded["metadata"]
    return {
        "status": "ready",
        "modelLoaded": True,
        "modelVersion": metadata.get("modelVersion"),
        "horizon": metadata.get("horizon"),
        "artifactCompatible": True,
        "precise": False,
        "note": "Readiness checks artifact presence and hash, not model accuracy.",
    }


@app.post("/predict")
@app.post("/v1/predictions")
def create_prediction(
    payload: dict[str, Any],
    request: Request,
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValidationError("Input payload must be a JSON object")
    return predict_from_payload(
        payload,
        request_id=x_request_id or getattr(request.state, "request_id", None),
    )
