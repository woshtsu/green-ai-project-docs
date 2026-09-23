from __future__ import annotations

from src.evaluation.comparison import select_model


def test_selects_lowest_mae():
    selected = select_model(
        [
            {"model": "xgboost", "horizon": "15m", "mae": 4.0, "rmse": 5.0, "smape": 10.0},
            {"model": "random_forest", "horizon": "15m", "mae": 3.0, "rmse": 4.0, "smape": 9.0},
            {"model": "persistence", "horizon": "15m", "mae": 6.0, "rmse": 7.0, "smape": 12.0},
        ],
        horizon="15m",
    )
    assert selected["model"] == "random_forest"


def test_prefers_simpler_model_when_mae_is_equivalent():
    selected = select_model(
        [
            {"model": "xgboost", "horizon": "15m", "mae": 3.00, "rmse": 4.0, "smape": 8.0},
            {"model": "persistence", "horizon": "15m", "mae": 3.01, "rmse": 4.1, "smape": 8.1},
        ],
        horizon="15m",
        equivalence_mae_relative=0.02,
    )
    assert selected["model"] == "persistence"
