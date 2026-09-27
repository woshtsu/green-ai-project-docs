# Fixtures

These files are **simulated / fixture** data. They exist so any teammate can
train, test and infer without live Monitoring or Data Processing.

They must never be presented as observed measurements or as evidence of
energy savings.

| File | Kind | Purpose |
|---|---|---|
| `dataprocessing_prediction_dataset.json` | fixture | Mirrors Data Processing `GET /api/v1/prediction/dataset` (15s CPU %) |
| `ml_name_value_unit.json` | fixture | Mirrors the name/value/unit contract in `ml.md` |
| `no_data.json` | fixture | `dataStatus=no_data`; ML must reject it without converting to zero |
| `sample_window.json` | simulated | 5-minute window used by local `/predict` checks |

Regenerate:

```bash
python scripts/prepare_dataset.py
```
