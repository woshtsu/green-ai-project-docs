# Model card

## Objective

Estimate future computational demand for one node, prioritizing CPU
utilization. Complementary variables (memory, requests, network) are used only
when they are present in the dataset and enabled in configuration.

A computational-demand prediction is **not** an energy measurement.

## Target

- Variable: `cpu_utilization`
- Unit: percent
- Horizons: 5 minutes, 15 minutes, 30 minutes
- Default serving horizon: 15 minutes

## Dataset

Default training uses the simulated fixture `data/raw/sample_dataset.json`
(`origin=simulated`). It is a technical fixture, not observed production data
and not evidence of energy savings.

## Features

Same logic in training and inference:

- current CPU
- hour, minute, day of week, day of month
- cyclic encodings (`hour_sin`, `hour_cos`, `dow_sin`, `dow_cos`)
- lags `cpu_lag_1`, `cpu_lag_2`, `cpu_lag_3`
- rolling mean/std/min/max over 3 and 6 steps

Lags and rolling windows use only information available at prediction time.

## Models

Candidates: Persistence, Moving Average, Random Forest, XGBoost.

Selection uses TRAIN for fitting and VALIDATION for comparison. TEST is
reported once after the selected model is retrained on TRAIN+VALIDATION.

## Recorded parameters

Random Forest: `n_estimators`, `max_depth`, `min_samples_leaf`,
`random_state`, `n_jobs`.

XGBoost: `n_estimators`, `learning_rate`, `max_depth`, `subsample`,
`colsample_bytree`, `objective`, `random_state`.

## Metrics

MAE, RMSE, sMAPE, peak/high-demand error, inference latency.

## Limitations

- Simulated fixture metrics do not prove production accuracy.
- CPU demand is not watts, kWh or CO2.
- Deep Learning is out of scope.
- The service does not execute optimizations.
