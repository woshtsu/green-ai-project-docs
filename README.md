# Computational demand prediction (ML)

Machine Learning component that estimates **short-term computational demand**, prioritizing `cpu_utilization` (%). It is the model core that Prediction Service will consume later.

This component does **not** query Prometheus, Supabase or Kubernetes, and it does **not** predict energy, kWh or CO2.

## Objective

Predict CPU demand at configurable horizons:

- 5 minutes
- 15 minutes
- 30 minutes

The serialized model corresponds to the configured default horizon (`15m`) and the model with the best experimental metrics for that horizon.

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

Python 3.10+ is required.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

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

Expected contract (Data Processing):

- `schemaVersion`, `datasetId`, `period`, `resource`
- `features` (time-series records)
- `origins`, `dataStatus`, `warnings`

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

Selection priority: MAE → RMSE → sMAPE → high-demand error → latency → complexity. If MAE values are equivalent, the simpler model wins.

## Tests

```bash
pytest
pytest --cov=src tests/
```

Coverage target: >= 80%.

## Selected model

Values below come from `python scripts/run_pipeline.py` on the simulated fixture `dataset-sim-001` (`origin=simulated`). They are **technical test results**, not experimental project results and not energy-savings claims.

| Field | Value |
| --- | --- |
| modelType | random_forest |
| horizon | 15m |
| target | cpu_utilization (%) |
| features | 23 (current CPU, temporal, lags 1-3, rolling 3/6, complementary current-time variables) |
| MAE | 3.987754 |
| RMSE | 5.530001 |
| sMAPE | 7.915891 |
| high-demand MAE | 4.711119 |
| mean latency | 17.23 ms |
| p95 latency | 20.74 ms |

Random Forest was selected for the configured default horizon (15m) because it had the lowest MAE among the 15m candidates. XGBoost was not chosen a priori.

```text
DECISIÓN TÉCNICA
Motivo: un horizonte más corto produce MAE menor de forma estructural.
Alternativas consideradas: menor MAE global; score normalizado por horizonte; mejor modelo del horizonte operativo.
Decisión: evaluar 5m/15m/30m; serializar el mejor modelo del horizonte configurado (15m); conservar la comparación completa.
Impacto: el artefacto selected es usable por Prediction Service a 15m sin ocultar los demás horizontes.
```

## MLflow

Local tracking directory: `./mlruns`.

| Field | Value |
| --- | --- |
| experiment | computational-demand-prediction |
| run_id | 956b313c15f74240b5a687da27c79c15 |
| registered model | computational-demand-model |
| model version | 1 |

## Inference

```python
from src.inference.predict import predict

result = predict({"cpu_utilization": 41.2, ...})
# result["origin"] == "estimated"
```

`predict()` does not call infrastructure. It only loads `models/selected/model.joblib`.

## Artifacts

After a successful pipeline run:

- `models/selected/model.joblib`
- `models/selected/metadata.json`
- `results/metrics/model_comparison.csv`
- `results/metrics/selected_model_metrics.json`
- `results/predictions/`
- `results/plots/`
- `results/reports/model_report.md`

## Limitations

- The bundled fixture is simulated. Metrics from it are **technical test results**, not project experimental results.
- The model predicts computational demand, not energy savings.
- Deep Learning is out of scope for this version.
- Feature importance is not causal.
- No automatic retraining. Drift comparison lives in `src/drift/monitor.py`.

## Future integration

Prediction Service should wrap `predict()` and emit:

`predictionId`, resource, target, `predictedFor`, value, unit, `modelVersion`, `inputDatasetId`, `origin=estimated`, `generatedAt`.

The FastAPI surface is intentionally not implemented here.
