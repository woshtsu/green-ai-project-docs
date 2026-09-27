# Computational demand prediction (ML)

Machine Learning component that estimates **short-term computational demand**,
prioritizing `cpu_utilization` (%).

It adapts to the existing Data Processing contract. Other repositories are
never modified from this component.

## What it does

- Validates a prepared dataset
- Builds leakage-safe features and targets
- Trains Persistence, Moving Average, Random Forest and XGBoost
- Selects a model on VALIDATION
- Serves a future CPU estimate through `POST /predict`

## What it does not do

- Query Prometheus, Supabase or Kubernetes
- Change workloads or apply optimizations
- Treat CPU as watts, kWh or CO2
- Present predictions as observations
- Convert `missing` / `null` / `no_data` into zero

## Architecture

```text
Data Processing JSON
    → ML Input Adapter
    → Validation / resampling
    → Features
    → Model
    → Output Adapter
    → prediction (origin=estimated)
```

Details: `docs/architecture.md`, `docs/data-contract.md`, `docs/model-card.md`,
`docs/experiments.md`.

## Installation

Python **3.11.9**.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.lock.txt
copy .env.example .env
```

On Linux/macOS use `source .venv/bin/activate` and `cp .env.example .env`.

## Training

```bash
python scripts/prepare_dataset.py
python scripts/run_pipeline.py
```

Equivalent aliases: `python scripts/train.py` and `python scripts/evaluate.py`.

The selected artifact is written to `models/selected/`. The process does not
train again when the API receives a request.

## Tests

```bash
pytest
pytest --cov=src tests/
```

## Inference

```bash
uvicorn src.service.app:app --host 0.0.0.0 --port 8000
```

```text
GET  /health
GET  /health/live
GET  /health/ready
POST /predict
POST /v1/predictions
```

CLI:

```bash
python scripts/predict.py --input data/fixtures/dataprocessing_prediction_dataset.json
```

## Docker

```bash
docker build -t green-ai-ml:local .
docker run --rm -p 8000:8000 green-ai-ml:local
```

Then open `http://127.0.0.1:8000/health` and send the fixture to
`POST /predict`.

## Contract

Input: Data Processing `GET /api/v1/prediction/dataset` or the name/value/unit
shape in `ml.md`. Conversion happens in `src/adapters/`.

Output: prediction contract with `origin=estimated`.

Errors:

| Status | Code |
|---|---|
| 400 | INVALID_INPUT |
| 422 | INVALID_DATASET |
| 503 | MODEL_UNAVAILABLE |
| 500 | INFERENCE_ERROR |

## Limitations

- Bundled fixtures are simulated. They check execution, not real accuracy.
- A demand prediction is not an energy measurement.
- Deep Learning is out of scope.
- Gateway and Frontend are not modified; they can consume this API later.
