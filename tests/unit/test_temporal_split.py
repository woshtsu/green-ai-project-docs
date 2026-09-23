from __future__ import annotations

import pandas as pd
import pytest

from src.exceptions import LeakageError, ValidationError
from src.preprocessing.temporal import assert_purged_boundaries, horizon_steps, infer_frequency, temporal_split


def test_horizon_must_be_exact_multiple_of_frequency():
    stamps = pd.date_range("2026-09-01", periods=12, freq="5min", tz="UTC")
    frequency = infer_frequency(pd.Series(stamps))
    assert horizon_steps("15m", frequency) == 3
    with pytest.raises(ValidationError, match="exact multiple"):
        horizon_steps("7m", frequency)


def test_unpurged_boundary_is_rejected():
    stamps = pd.date_range("2026-09-01", periods=30, freq="5min", tz="UTC")
    frame = pd.DataFrame({"timestamp": stamps, "cpu_utilization": range(30)})
    train, validation, test = frame.iloc[:10], frame.iloc[10:20], frame.iloc[20:]
    with pytest.raises(LeakageError, match="not purged"):
        assert_purged_boundaries(train, validation, test, "15m")


def test_temporal_split_purges_horizon():
    stamps = pd.date_range("2026-09-01", periods=40, freq="5min", tz="UTC")
    frame = pd.DataFrame({"timestamp": stamps, "cpu_utilization": range(40)})
    train, validation, test = temporal_split(frame, horizon="15m")
    assert train["timestamp"].max() + pd.Timedelta(minutes=15) < validation["timestamp"].min()
    assert validation["timestamp"].max() + pd.Timedelta(minutes=15) < test["timestamp"].min()
