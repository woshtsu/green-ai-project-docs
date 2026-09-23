"""Versioned internal Prediction API.

Does not query Prometheus, Supabase or Kubernetes. Callers are Gateway/Decision.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.config.settings import load_config
from src.exceptions import ArtifactIntegrityError, InsufficientDataError, MLError, ModelNotFoundError
from src.inference.predict import load_selected_model, predict_from_window

LOGGER = logging.getLogger(__name__)
MAX_RECORDS = 5000

app = FastAPI(
    title="Prediction Service",
    version="1.0.0",
    description="Internal API for short-term CPU demand estimates.",
)


class Resource(BaseModel):
    type: str
    cluster: str
    id: str


class DatasetWindow(BaseModel):
    schemaVersion: str = "1.0"
    datasetId: str | None = None
    resource: Resource | None = None
    features: list[dict[str, Any]] = Field(..., min_length=2, max_length=MAX_RECORDS)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response


@app.exception_handler(MLError)
async def ml_error_handler(request: Request, exc: MLError) -> JSONResponse:
    status = 404 if isinstance(exc, ModelNotFoundError) else 400
    if isinstance(exc, ArtifactIntegrityError):
        status = 409
    if isinstance(exc, InsufficientDataError):
        status = 422
    return JSONResponse(
        status_code=status,
        content={"code": exc.code, "message": exc.message, "details": exc.details},
        headers={"X-Request-Id": getattr(request.state, "request_id", "")},
    )


@app.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "live"}


@app.get("/health/ready")
def readiness() -> dict[str, Any]:
    loaded = load_selected_model()
    metadata = loaded["metadata"]
    return {
        "status": "ready",
        "modelVersion": metadata.get("modelVersion"),
        "horizon": metadata.get("horizon"),
        "artifactCompatible": True,
        "precise": False,
        "note": "Readiness checks artifact presence and hash, not model accuracy.",
    }


@app.post("/v1/predictions")
def create_prediction(
    payload: DatasetWindow,
    request: Request,
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
) -> dict[str, Any]:
    if payload.schemaVersion != "1.0":
        raise HTTPException(status_code=400, detail="Unsupported schemaVersion")
    config = load_config()
    result = predict_from_window(
        payload.features,
        config=config,
        request_id=x_request_id or getattr(request.state, "request_id", None),
    )
    if payload.resource:
        result["resource"] = payload.resource.model_dump()
    if payload.datasetId:
        result["inputDatasetId"] = payload.datasetId
    return {
        "predictionId": result["predictionId"],
        "resource": result.get("resource"),
        "target": result["target"],
        "predictedFor": result.get("predictedFor"),
        "generatedAt": result.get("generatedAt"),
        "value": result["value"],
        "unit": result["unit"],
        "horizon": result["horizon"],
        "modelVersion": result.get("modelVersion"),
        "inputDatasetId": result.get("inputDatasetId"),
        "origin": "estimated",
    }
