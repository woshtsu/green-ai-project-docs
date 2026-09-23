"""Model evaluation including high-demand and load-band slices."""

from __future__ import annotations

import time
from typing import Any, Callable

import numpy as np
import pandas as pd

from src.evaluation.metrics import latency_stats, mae, rmse, smape
from src.exceptions import ValidationError


def evaluate_predictions(
    y_true: pd.Series | np.ndarray,
    y_pred: np.ndarray,
    config: dict[str, Any] | None = None,
    predict_fn: Callable[[], np.ndarray] | None = None,
    repeats: int | None = None,
) -> dict[str, Any]:
    true_values = np.asarray(y_true, dtype=float)
    pred_values = np.asarray(y_pred, dtype=float)
    if true_values.shape != pred_values.shape:
        raise ValidationError("Prediction and target shapes do not match")
    if np.isnan(pred_values).any():
        raise ValidationError("Predictions contain NaN")

    metrics: dict[str, Any] = {
        "mae": mae(true_values, pred_values),
        "rmse": rmse(true_values, pred_values),
        "smape": smape(true_values, pred_values),
        "n_samples": int(true_values.size),
    }

    cfg = config or {}
    high_cfg = cfg.get("high_demand", {})
    high_percentile = float(high_cfg.get("percentile", 75))
    peak_percentile = float(high_cfg.get("peak_percentile", 90))
    bands_cfg = cfg.get("load_bands", {})

    metrics.update(_slice_metrics(true_values, pred_values, "high_demand", high_percentile, "gte"))
    metrics.update(_slice_metrics(true_values, pred_values, "peak", peak_percentile, "gte"))
    metrics.update(
        _named_band_metrics(
            true_values,
            pred_values,
            low_cut=float(bands_cfg.get("low_percentile", 33)),
            high_cut=float(bands_cfg.get("high_percentile", 66)),
        )
    )

    repeat_count = repeats if repeats is not None else int(cfg.get("latency_repeats", 1))
    metrics.update(measure_latency(predict_fn, repeats=repeat_count))
    return metrics


def measure_latency(predict_fn: Callable[[], np.ndarray] | None, repeats: int = 1) -> dict[str, float]:
    if predict_fn is None or repeats < 1:
        return {"latency_mean_ms": float("nan"), "latency_p50_ms": float("nan"), "latency_p95_ms": float("nan")}
    samples: list[float] = []
    for _ in range(repeats):
        started = time.perf_counter()
        predict_fn()
        samples.append((time.perf_counter() - started) * 1000.0)
    return latency_stats(samples)


def _slice_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    prefix: str,
    percentile: float,
    mode: str,
) -> dict[str, Any]:
    threshold = float(np.percentile(y_true, percentile))
    mask = y_true >= threshold if mode == "gte" else y_true <= threshold
    if mask.sum() < 1:
        return {
            f"{prefix}_mae": None,
            f"{prefix}_rmse": None,
            f"{prefix}_smape": None,
            f"{prefix}_n": 0,
            f"{prefix}_threshold": threshold,
        }
    return {
        f"{prefix}_mae": mae(y_true[mask], y_pred[mask]),
        f"{prefix}_rmse": rmse(y_true[mask], y_pred[mask]),
        f"{prefix}_smape": smape(y_true[mask], y_pred[mask]),
        f"{prefix}_n": int(mask.sum()),
        f"{prefix}_threshold": threshold,
    }


def _named_band_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    low_cut: float,
    high_cut: float,
) -> dict[str, Any]:
    low_thr = float(np.percentile(y_true, low_cut))
    high_thr = float(np.percentile(y_true, high_cut))
    bands = {
        "low_load": y_true <= low_thr,
        "normal_load": (y_true > low_thr) & (y_true < high_thr),
        "high_load": y_true >= high_thr,
    }
    report: dict[str, Any] = {}
    for name, mask in bands.items():
        if mask.sum() < 1:
            report[f"{name}_mae"] = None
            report[f"{name}_n"] = 0
            continue
        report[f"{name}_mae"] = mae(y_true[mask], y_pred[mask])
        report[f"{name}_rmse"] = rmse(y_true[mask], y_pred[mask])
        report[f"{name}_smape"] = smape(y_true[mask], y_pred[mask])
        report[f"{name}_n"] = int(mask.sum())
    report["low_load_threshold"] = low_thr
    report["high_load_threshold"] = high_thr
    return report
