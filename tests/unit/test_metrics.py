from __future__ import annotations

import math

import pytest

from src.evaluation.metrics import mae, rmse, smape


def test_mae_known_values():
    assert mae([1, 2, 3], [1, 2, 4]) == pytest.approx(1 / 3)


def test_rmse_known_values():
    assert rmse([1, 2, 3], [1, 2, 4]) == pytest.approx(math.sqrt(1 / 3))


def test_smape_known_values():
    expected = ((0 + 0 + 2 * 1 / (3 + 4)) / 3) * 100
    assert smape([1, 2, 3], [1, 2, 4]) == pytest.approx(expected)


def test_smape_is_stable_near_zero():
    value = smape([0.0, 0.0], [0.0, 0.0])
    assert math.isfinite(value)
    assert value == pytest.approx(0.0)


def test_metrics_reject_nan():
    with pytest.raises(ValueError):
        mae([1.0, float("nan")], [1.0, 2.0])


def test_shape_mismatch_is_rejected():
    with pytest.raises(ValueError):
        rmse([1.0, 2.0], [1.0])
