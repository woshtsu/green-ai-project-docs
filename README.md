# Computational demand prediction (ML)

Machine Learning component that estimates **short-term computational demand**, prioritizing `cpu_utilization` (%). It is the model core that Prediction Service will consume later.

This component does **not** query Prometheus, Supabase or Kubernetes, and it does **not** predict energy, kWh or CO2.

## Objective

Predict CPU demand at configurable horizons:

- 5 minutes
- 15 minutes
- 30 minutes

Status of this increment: **experimental ML core on a simulated fixture**. It is not a validated operational model and not an integrated Prediction Service in the platform flow.

Candidates are fit on TRAIN, selected on VALIDATION, retrained on TRAIN+VALIDATION, and reported once on TEST. Partition boundaries are purged by at least one forecast horizon.

## Architecture

```text
Monitoring
    → Data Processing
        → ML / Prediction core (this component)
            → Decision / Optimization / Policy / Recommendation
```

Internal flow:

```text
dataset → validate → clean → features → temporal split
      → persistence / moving average / Random Forest / XGBoost
      → evaluation → selection → MLflow → model.joblib
```

## Installation

Python **3.11.9** (see `.python-version`).

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.lock.txt
```

`requirements.txt` keeps compatible ranges. `requirements.lock.txt` pins the versions used for this increment.

## Dependencies

See `requirements.txt`. Versions actually installed for this technical run (Python 3.11.9):

```text
pandas==2.3.3
numpy==2.4.6
scikit-learn==1.9.1
xgboost==2.1.4
matplotlib==3.11.2
seaborn==0.13.2
pyyaml==6.0.3
joblib==1.6.0
mlflow==2.22.5
pytest==8.4.2
pytest-cov==5.0.0
statsmodels==0.15.0
```

## Dataset

Published contract (v1): `contracts/dataset-v1.schema.json`.

- One resource per dataset
- `features` is a list of temporal records (`timestamp`, `cpu_utilization`, `origin`, `quality`), not Monitoring `name/value/unit` objects
- Units: CPU and memory utilization in **percent**; `network_*` in bytes/s; `cpu_requests` in cores; `memory_requests` in MiB
- Monitoring ratio/bytes must be converted **before** this contract
- Unknown `schemaVersion` is rejected
- Mixed origins are rejected unless `data.allow_mixed_origins` is set as an explicit mix operation

This fixture does **not** demonstrate Data Processing integration until both sides emit the same schema.

If no official Data Processing dataset is present, the pipeline generates a **simulated** fixture:

```text
data/raw/sample_dataset.json
```

Every generated record has `origin = simulated`. It must never be presented as a real observation.

```bash
python scripts/prepare_dataset.py
```

## Structure

```text
ML/
├── config/config.yaml
├── src/                 # productive logic
├── tests/               # unit + integration
├── scripts/             # CLI entry points
├── notebooks/           # EDA only
├── models/selected/     # model.joblib + metadata.json
└── results/             # metrics, predictions, plots, report
```

## Configuration

`config/config.yaml` controls horizons, split ratios, features, model hyperparameters, MLflow and paths. Do not hardcode a single 15-minute horizon in code.

## Training

```bash
python scripts/run_pipeline.py
```

Equivalent steps:

```bash
python scripts/prepare_dataset.py
python scripts/train_models.py
python scripts/evaluate_models.py
```

## Evaluation

Mandatory metrics: MAE, RMSE, sMAPE, plus latency and high-demand slices when the test split allows it.

Selection uses **VALIDATION** metrics only (MAE → RMSE → sMAPE → high-demand → latency → complexity). TEST is evaluated once after retraining and is not used to change the model. Validation and test metrics are stored separately.

## Tests

```bash
pytest
pytest --cov=src tests/
```

Coverage target: >= 80%.

## Selected model

Do not treat README numbers as evidence. Generated binaries (`model.joblib`, plots, `mlruns`) are gitignored. After a local or CI run, consult:

- `results/manifest.json` (commit, dataset hash, config hash, seed, validation/test metrics, artifact hashes)
- `results/metrics/selected_validation_metrics.json`
- `results/metrics/selected_test_metrics.json`

Those files are produced by `python scripts/run_pipeline.py` and are **technical results on `origin=simulated` data**.

## MLflow

Local tracking directory: `./mlruns` (gitignored). A run ID printed on a developer machine is not evidence in the branch. Use `results/manifest.json` plus CI artifacts.

## Inference

Preferred path: send a raw temporal window. The service applies the same preprocessing as training.

```python
from src.inference.predict import predict_from_window

result = predict_from_window(records)
# predictionId, predictedFor, generatedAt, origin=estimated
```

Internal API:

```bash
uvicorn src.service.app:app --port 8000
# GET  /health/live
# GET  /health/ready   (artifact + hash only; does not claim accuracy)
# POST /v1/predictions
```

`predict()` still accepts engineered features for tests. Production callers should use the window API to avoid training-serving skew.

## Artifacts

After a successful pipeline run (local/CI, not committed):

- `models/selected/model.joblib` + `metadata.json` (`modelSha256`)
- `results/manifest.json`
- `results/metrics/validation_comparison.csv`
- `results/metrics/selected_validation_metrics.json`
- `results/metrics/selected_test_metrics.json`
- `results/predictions/`
- `results/plots/`
- `results/reports/model_report.md`

## Limitations

- The bundled fixture is simulated. It checks execution, not generalization to observed data.
- The model predicts computational demand, not energy savings.
- Deep Learning is out of scope for this version.
- Feature importance is not causal.
- Drift compare/persist exists; no automatic retraining.
- Gateway/Decision routing and observed-data backtesting are still pending.
