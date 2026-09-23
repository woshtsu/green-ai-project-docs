from __future__ import annotations

import numpy as np
import pytest

from src.drift.monitor import compare_distributions, compare_errors


def test_identical_distributions_have_low_psi():
    values = np.linspace(10, 40, 80)
    report = compare_distributions(values, values)
    assert report["psi"] < 0.1
    assert report["retraining"] is False


def test_shifted_distribution_can_alert():
    training = np.linspace(10, 20, 80)
    recent = np.linspace(40, 50, 80)
    report = compare_distributions(training, recent)
    assert report["alert"] is True
    assert report["retraining"] is False


def test_error_comparison_flags_degradation():
    report = compare_errors(np.ones(30), np.ones(30) * 3)
    assert report["recent_mae"] > report["historical_mae"]
    assert report["alert"] is True
    assert report["retraining"] is False


def test_empty_series_are_rejected():
    with pytest.raises(Exception):
        compare_distributions([], [1.0])
