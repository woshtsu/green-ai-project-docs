"""Prediction-owned recommendation and energy HTTP adapters."""
import math
import os
from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import uuid4

from src.inference.predict import predict_from_payload
from src.recommendations.policy import evaluate_policy

from fastapi import APIRouter, HTTPException, Request, Response
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime, ValidationError, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Problem(Model):
    detail: str


class InferenceProblem(Model):
    code: str
    message: str
    details: dict


Percent = Annotated[float, Field(ge=0, le=100)]


class Policy(Model):
    mode: Literal['demonstration'] = 'demonstration'
    cpuLowPercent: Percent = 30
    cpuHighPercent: Percent = 80
    memoryMaxPercent: Percent = 85
    latencyP95MaxMs: float = Field(default=500, gt=0)
    errorRateMaxPercent: Percent = 1
    freshnessSeconds: int = Field(default=300, ge=1, le=3600)

    @model_validator(mode='after')
    def ordered(self):
        if self.cpuLowPercent >= self.cpuHighPercent:
            raise ValueError('CPU low threshold must be below high threshold')
        return self


# Invalid configuration prevents startup instead of silently weakening the policy.
policy = Policy.model_validate_json(os.environ.get('DEMO_POLICY_JSON', '{}'))
router = APIRouter(tags=["Recommendations"])
decisions = Counter('green_ai_recommendations', 'Demo evaluations by result', ['status'])
energy_value = Gauge('green_ai_last_energy_kwh', 'Last imported period energy, NOT cumulative consumption', ['origin'])
energy_time = Gauge('green_ai_last_energy_calculated_timestamp_seconds', 'Time of last energy calculation', ['origin'])
cpu_value = Gauge('green_ai_last_prediction_cpu_percent', 'Last CPU estimate consulted, NOT a fleet average')
cpu_time = Gauge('green_ai_last_prediction_generated_timestamp_seconds', 'Generation time of last consulted prediction')


@router.get('/metrics', include_in_schema=False)
def metrics():
    return Response(generate_latest(), headers={'Content-Type': CONTENT_TYPE_LATEST})


class Resource(Model):
    type: Literal['node']
    id: str = Field(min_length=1, max_length=200)
    cluster: str = Field(min_length=1, max_length=200)


class Telemetry(Model):
    resource: Resource
    observedAt: AwareDatetime
    origin: Literal['observed', 'simulated']
    memoryPercent: Percent | None = None
    latencyP95Ms: float | None = Field(default=None, ge=0)
    errorRatePercent: Percent | None = None


class RecommendationRequest(Model):
    dataset: dict
    telemetry: Telemetry | None = None


class Prediction(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    resource: Resource
    inputDatasetId: str
    predictionId: str
    target: Literal['cpu_utilization']
    unit: Literal['%']
    origin: Literal['estimated']
    value: Percent
    generatedAt: AwareDatetime
    predictedFor: AwareDatetime


class Check(Model):
    name: str
    status: Literal['pass', 'fail', 'unknown']


class Recommendation(Model):
    recommendationId: str
    generatedAt: AwareDatetime
    predictionId: str
    inputDatasetId: str
    predictedCpuPercent: Percent
    telemetry: Telemetry | None
    resource: Resource
    status: Literal['not_evaluable', 'blocked', 'eligible_for_review']
    action: Literal['none', 'maintain', 'review_capacity_reduction', 'review_capacity_increase']
    executionAllowed: Literal[False] = False
    policy: Policy
    checks: list[Check]
    warnings: list[str]


@router.post('/v1/recommendations', response_model=Recommendation,
          responses={400: {'model': InferenceProblem},
                     422: {'model': Problem | InferenceProblem},
                     502: {'model': Problem}, 503: {'model': InferenceProblem}})
def recommend(body: RecommendationRequest, request: Request):
    dataset = body.dataset
    try:
        resource = Resource.model_validate(dataset.get('resource'))
        if not isinstance(dataset.get('datasetId'), str) or not dataset['datasetId'].strip():
            raise ValueError('missing dataset id')
    except (ValidationError, ValueError):
        raise HTTPException(422, 'Dataset sin identidad de recurso válida.') from None
    raw = predict_from_payload(dataset, request_id=request.state.request_id)
    try:
        prediction = Prediction.model_validate(raw)
        if prediction.resource != resource or prediction.inputDatasetId != dataset['datasetId']:
            raise ValueError('mismatch')
    except (ValidationError, ValueError):
        raise HTTPException(502, 'Prediction devolvió un resultado incompatible con el dataset.') from None
    now = datetime.now(timezone.utc)
    telemetry = body.telemetry
    status, action, checks = evaluate_policy(
        prediction.model_dump(), telemetry.model_dump() if telemetry else None,
        policy.model_dump(), now)
    decisions.labels(status).inc()
    cpu_value.set(prediction.value)
    cpu_time.set(prediction.generatedAt.timestamp())
    return Recommendation(recommendationId=str(uuid4()), generatedAt=now,
        predictionId=prediction.predictionId, inputDatasetId=prediction.inputDatasetId,
        predictedCpuPercent=prediction.value, telemetry=telemetry, resource=resource, status=status, action=action,
        policy=policy, checks=checks, warnings=[
            'Umbrales de demostración; no representan SLA aprobados.',
            'Telemetría proporcionada por el operador, sin verificación independiente.',
            'La evaluación actual no garantiza el SLA futuro ni cuantifica ahorro. Requiere revisión humana.'])


class PowerSample(Model):
    timestamp: AwareDatetime
    watts: float = Field(ge=0, le=1e12)


class EnergyRequest(Model):
    origin: Literal['observed', 'simulated', 'estimated']
    samples: list[PowerSample] = Field(min_length=2, max_length=10000)
    emissionFactorKgPerKwh: float | None = Field(default=None, ge=0, le=100)
    emissionFactorSource: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode='after')
    def factor_source(self):
        if self.emissionFactorKgPerKwh is not None and not (self.emissionFactorSource or '').strip():
            raise ValueError('An emission factor requires its source')
        return self


class EnergyResult(Model):
    origin: str
    energyKwh: float
    co2eKg: float | None
    start: AwareDatetime
    end: AwareDatetime
    emissionFactorKgPerKwh: float | None
    emissionFactorSource: str | None
    method: str = 'trapezoidal_power_integration'
    warnings: list[str]


@router.post('/v1/energy', response_model=EnergyResult, responses={422: {'model': Problem}})
def energy(body: EnergyRequest):
    joules = []
    for left, right in zip(body.samples, body.samples[1:]):
        seconds = (right.timestamp - left.timestamp).total_seconds()
        if not 0 < seconds <= 300:
            raise HTTPException(422, 'Las muestras deben estar ordenadas, sin duplicados ni huecos mayores a 300 s.')
        joules.append((left.watts + right.watts) / 2 * seconds)
    kwh = math.fsum(joules) / 3600000
    energy_value.labels(body.origin).set(kwh)
    energy_time.labels(body.origin).set(datetime.now(timezone.utc).timestamp())
    return EnergyResult(origin=body.origin, energyKwh=kwh,
        co2eKg=None if body.emissionFactorKgPerKwh is None else kwh * body.emissionFactorKgPerKwh,
        start=body.samples[0].timestamp, end=body.samples[-1].timestamp,
        emissionFactorKgPerKwh=body.emissionFactorKgPerKwh, emissionFactorSource=body.emissionFactorSource,
        warnings=['Procedencia declarada por el operador. Energía integrada entre muestras; no demuestra ahorro.'])
