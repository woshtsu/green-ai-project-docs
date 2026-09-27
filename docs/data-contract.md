# Data contract

## Input

ML consumes the Data Processing prediction dataset. The live service emits
temporal CPU records:

```json
{
  "schemaVersion": "1.0",
  "contractStatus": "provisional",
  "datasetId": "dataset-...",
  "period": {"start": "RFC3339", "end": "RFC3339"},
  "resource": {"type": "node", "cluster": "...", "id": "..."},
  "features": [
    {
      "timestamp": "RFC3339",
      "cpu_utilization": 41.2,
      "origin": "simulated",
      "quality": "ok"
    }
  ],
  "units": {"cpu_utilization": "%"},
  "origins": ["simulated"],
  "dataStatus": "partial",
  "warnings": []
}
```

The adapter also accepts the name/value/unit shape described in `ml.md`.

Rules:

- `cpu_utilization` is percent 0-100. A Monitoring ratio is multiplied by 100
  only when the unit is `ratio`.
- `dataStatus=no_data` is rejected. It is not converted to zero.
- Missing, null and `no_data` tokens become NaN, never 0.
- 15-second windows are resampled to the model frequency (5 minutes). Empty
  bins are dropped.
- Extra Data Processing fields (`contractStatus`, `requestedPeriod`,
  `excludedSampleCount`) are ignored by the model and preserved in metadata.

## Output

```json
{
  "predictionId": "pred-...",
  "resource": {"type": "node", "cluster": "...", "id": "..."},
  "target": "cpu_utilization",
  "predictedFor": "RFC3339",
  "value": 0.0,
  "unit": "%",
  "modelVersion": "1.0.0",
  "inputDatasetId": "dataset-...",
  "origin": "estimated",
  "generatedAt": "RFC3339"
}
```

`origin` is always `estimated`. A prediction is never an observation and never
an energy measurement.
