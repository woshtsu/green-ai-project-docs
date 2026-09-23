from __future__ import annotations

import pandas as pd
import pytest

from src.exceptions import LeakageError
from src.preprocessing.features import (
    add_lags,
    add_rolling_features,
    add_target,
    add_temporal_features,
    assert_no_future_features,
    build_supervised_frame,
)
from src.preprocessing.temporal import infer_frequency


def _series(values, start="2026-09-01T00:00:00Z", minutes=5) -> pd.DataFrame:
    stamps = pd.date_range(start, periods=len(values), freq=f"{minutes}min", tz="UTC")
    return pd.DataFrame(
        {
            "timestamp": stamps,
            "cpu_utilization": values,
            "memory_utilization": [v * 0.8 for v in values],
            "origin": "simulated",
            "quality": "ok",
        }
    )


def test_temporal_features_are_derived_from_timestamp():
    frame = add_temporal_features(_series([10, 11, 12]))
    assert list(frame["hour"]) == [0, 0, 0]
    assert list(frame["minute"]) == [0, 5, 10]
    assert list(frame["day_of_week"]) == [1, 1, 1]
    assert list(frame["day_of_month"]) == [1, 1, 1]


def test_lags_use_only_past_values():
    frame = add_lags(_series([10, 20, 30, 40]), lags=[1, 2, 3])
    assert pd.isna(frame.loc[0, "cpu_lag_1"])
    assert frame.loc[1, "cpu_lag_1"] == 10
    assert frame.loc[3, "cpu_lag_2"] == 20
    assert frame.loc[3, "cpu_lag_3"] == 10


def test_negative_lag_is_rejected():
    with pytest.raises(LeakageError):
        add_lags(_series([10, 20, 30]), lags=[-1])


def test_rolling_features_exist_and_use_window():
    frame = add_rolling_features(_series([10, 20, 30, 40]), windows=[3], primary_window=3)
    assert pd.isna(frame.loc[1, "cpu_rolling_mean"])
    assert frame.loc[2, "cpu_rolling_mean"] == pytest.approx(20.0)


def test_target_shift_uses_real_frequency():
    frame = _series([10, 20, 30, 40, 50, 60, 70], minutes=5)
    frequency = infer_frequency(frame["timestamp"])
    result = add_target(frame, horizon="15m", frequency=frequency)
    assert result.attrs["horizon_steps"] == 3
    assert result.loc[0, "target"] == 40
    assert pd.isna(result.loc[4, "target"])


def test_rows_without_target_are_dropped(config):
    frame = _series(list(range(20, 80)))
    supervised, features, frequency, steps = build_supervised_frame(frame, config, "15m")
    assert steps == 3
    assert str(frequency) == "0 days 00:05:00"
    assert supervised["target"].notna().all()
    assert supervised[features].notna().all().all()
    assert supervised["timestamp"].is_monotonic_increasing


def test_future_feature_name_is_rejected():
    with pytest.raises(LeakageError, match="cpu_future_15m"):
        assert_no_future_features(["cpu_utilization", "cpu_future_15m"])


def test_target_column_cannot_enter_feature_list():
    with pytest.raises(LeakageError):
        assert_no_future_features(["cpu_utilization", "target"])
