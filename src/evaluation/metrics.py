"""Error and latency metrics."""

from __future__ import annotations

from typing import Any

import numpy as np

SMAPE_EPSILON = 1e-8


def _as_arrays(y_true: Any, y_pred: Any) -> tuple[np.ndarray, np.ndarray]:
    true_values = np.asarray(y_true, dtype=float)
    pred_values = np.asarray(y_pred, dtype=float)
    if true_values.shape != pred_values.shape:
        raise ValueError("y_true and y_pred must have the same shape")
    if true_values.size == 0:
        raise ValueError("Cannot compute metrics on empty arrays")
    if np.isnan(true_values).any() or np.isnan(pred_values).any():
        raise ValueError("Metrics cannot be computed when NaN is present")
    return true_values, pred_values


def mae(y_true: Any, y_pred: Any) -> float:
    true_values, pred_values = _as_arrays(y_true, y_pred)
    return float(np.mean(np.abs(true_values - pred_values)))


def rmse(y_true: Any, y_pred: Any) -> float:
    true_values, pred_values = _as_arrays(y_true, y_pred)
    return float(np.sqrt(np.mean((true_values - pred_values) ** 2)))


def smape(y_true: Any, y_pred: Any, epsilon: float = SMAPE_EPSILON) -> float:
    """Symmetric MAPE that remains defined when both values are near zero."""
    true_values, pred_values = _as_arrays(y_true, y_pred)
    denominator = np.abs(true_values) + np.abs(pred_values) + epsilon
    return float(np.mean(2.0 * np.abs(true_values - pred_values) / denominator) * 100.0)


def latency_stats(latencies_ms: list[float] | np.ndarray) -> dict[str, float]:
    values = np.asarray(latencies_ms, dtype=float)
    if values.size == 0:
        return {"latency_mean_ms": float("nan"), "latency_p50_ms": float("nan"), "latency_p95_ms": float("nan")}
    return {
        "latency_mean_ms": float(np.mean(values)),
        "latency_p50_ms": float(np.percentile(values, 50)),
        "latency_p95_ms": float(np.percentile(values, 95) if values.size >= 2 else values[0]),
    }
