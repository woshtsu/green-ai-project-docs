# Experiments

Local tracking uses MLflow at `./mlruns` when the library is available. If a
remote tracking server is absent, training still completes and writes:

- `models/selected/model.joblib`
- `models/selected/metadata.json`
- `results/manifest.json`
- `results/metrics/selected_validation_metrics.json`
- `results/metrics/selected_test_metrics.json`
- `results/reports/model_report.md`

## Protocol

1. Fit every candidate on TRAIN for horizons 5m, 15m and 30m.
2. Compare MAE → RMSE → sMAPE → high-demand error → latency → complexity on
   VALIDATION.
3. Retrain the winner on TRAIN+VALIDATION.
4. Score TEST once. Do not change the winner using TEST.

## How to reproduce

```bash
python scripts/prepare_dataset.py
python scripts/run_pipeline.py --skip-mlflow
```

Interpret every number as a technical result on `origin=simulated` data unless
an observed dataset is supplied.
