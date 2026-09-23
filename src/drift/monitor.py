"""Drift support. Compares distributions and errors. No automatic retraining."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.exceptions import ValidationError


def compare_distributions(
    training: pd.Series | np.ndarray,
    recent: pd.Series | np.ndarray,
    bins: int = 10,
) -> dict[str, Any]:
    """Compare a training distribution against a recent window."""
    train_values = _finite_array(training)
    recent_values = _finite_array(recent)
    if train_values.size == 0 or recent_values.size == 0:
        raise ValidationError("Both distributions must contain numeric values")

    edges = np.histogram_bin_edges(train_values, bins=bins)
    train_hist, _ = np.histogram(train_values, bins=edges)
    recent_clipped = np.clip(recent_values, edges[0], edges[-1])
    recent_hist, _ = np.histogram(recent_clipped, bins=edges)
    psi = population_stability_index(train_hist, recent_hist)
    return {
        "training_mean": float(np.mean(train_values)),
        "recent_mean": float(np.mean(recent_values)),
        "training_std": float(np.std(train_values)),
        "recent_std": float(np.std(recent_values)),
        "mean_delta": float(np.mean(recent_values) - np.mean(train_values)),
        "psi": psi,
        "alert": bool(psi >= 0.2),
        "retraining": False,
        "threshold": 0.2,
        "reference": "training_distribution",
        "compared": "recent_distribution",
    }


def compare_errors(
    historical_errors: pd.Series | np.ndarray,
    recent_errors: pd.Series | np.ndarray,
) -> dict[str, Any]:
    hist = np.abs(_finite_array(historical_errors))
    recent = np.abs(_finite_array(recent_errors))
    if hist.size == 0 or recent.size == 0:
        raise ValidationError("Both error series must contain numeric values")
    hist_mae = float(np.mean(hist))
    recent_mae = float(np.mean(recent))
    return {
        "historical_mae": hist_mae,
        "recent_mae": recent_mae,
        "mae_delta": recent_mae - hist_mae,
        "alert": bool(recent_mae > hist_mae * 1.25 and recent_mae - hist_mae > 1.0),
        "retraining": False,
        "threshold": 1.25,
        "reference": "historical_error",
        "compared": "recent_error",
    }


def persist_alert(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")


def population_stability_index(expected_counts: np.ndarray, actual_counts: np.ndarray) -> float:
    expected = np.asarray(expected_counts, dtype=float)
    actual = np.asarray(actual_counts, dtype=float)
    expected = (expected + 1e-6) / (expected.sum() + 1e-6 * expected.size)
    actual = (actual + 1e-6) / (actual.sum() + 1e-6 * actual.size)
    return float(np.sum((actual - expected) * np.log(actual / expected)))


def _finite_array(values: pd.Series | np.ndarray) -> np.ndarray:
    array = pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(dtype=float)
    return array[np.isfinite(array)]
