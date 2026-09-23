"""Compare trained models and select one from experimental metrics."""

from __future__ import annotations

from typing import Any

import pandas as pd

COMPLEXITY_RANK = {
    "persistence": 0,
    "moving_average": 1,
    "random_forest": 2,
    "xgboost": 3,
}


def comparison_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    expected = [
        "model",
        "horizon",
        "mae",
        "rmse",
        "smape",
        "latency_mean_ms",
        "high_demand_mae",
        "high_demand_rmse",
        "high_demand_smape",
    ]
    for column in expected:
        if column not in frame.columns:
            frame[column] = None
    return frame[expected + [col for col in frame.columns if col not in expected]]


def select_model(
    rows: list[dict[str, Any]],
    horizon: str,
    equivalence_mae_relative: float = 0.02,
) -> dict[str, Any]:
    """Select the best model for the configured horizon.

    Priority: MAE, RMSE, sMAPE, high-demand MAE, latency, complexity.
    If MAE values are equivalent, prefer the simpler model.
    """
    candidates = [row for row in rows if row.get("horizon") == horizon]
    if not candidates:
        raise ValueError(f"No evaluation rows for horizon {horizon}")

    ranked = sorted(candidates, key=lambda row: _sort_key(row))
    best = ranked[0]
    for candidate in ranked[1:]:
        if _mae_equivalent(best, candidate, equivalence_mae_relative) and _complexity(candidate) < _complexity(best):
            best = candidate
    return best


def _sort_key(row: dict[str, Any]) -> tuple:
    return (
        _finite(row.get("mae")),
        _finite(row.get("rmse")),
        _finite(row.get("smape")),
        _finite(row.get("high_demand_mae")),
        _finite(row.get("latency_mean_ms")),
        _complexity(row),
    )


def _mae_equivalent(left: dict[str, Any], right: dict[str, Any], tolerance: float) -> bool:
    left_mae = _finite(left.get("mae"))
    right_mae = _finite(right.get("mae"))
    baseline = max(left_mae, 1e-9)
    return abs(left_mae - right_mae) / baseline <= tolerance


def _complexity(row: dict[str, Any]) -> int:
    return COMPLEXITY_RANK.get(str(row.get("model", "")), 99)


def _finite(value: Any) -> float:
    if value is None:
        return float("inf")
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float("inf")
    if pd.isna(number):
        return float("inf")
    return number
