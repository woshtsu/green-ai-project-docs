# Architecture

The ML component estimates short-term computational demand. It occupies only
this slice of the platform:

```text
Data Processing → Prediction ML → Decision
```

It does not query Prometheus, Supabase or Kubernetes, and it does not apply
optimization, policies or workload changes.

## Internal flow

```text
Input Adapter
    → Validation
    → Normalization / resampling
    → Feature engineering
    → Window and target construction
    → Temporal TRAIN / VALIDATION / TEST split
    → Persistence and moving-average baselines
    → Random Forest
    → XGBoost
    → Evaluation
    → Selection on VALIDATION
    → Final training on TRAIN+VALIDATION
    → Serialization
    → Inference
    → Output Adapter
```

## Adaptation rule

External contracts stay unchanged. If Data Processing sends extra fields,
15-second samples, `dataStatus=no_data`, or name/value/unit features, the
conversion happens inside `src/adapters/`.

## Serving

```text
Start process
    → load models/selected/model.joblib
    → receive POST /predict
    → adapt → features → infer
    → return origin=estimated
```

The service never trains during a request.

## Ports

The API listens on **8000**. That value comes from this repository, not from
other services.
