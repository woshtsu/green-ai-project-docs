from __future__ import annotations

import pandas as pd
import pytest

from src.exceptions import LeakageError
from src.preprocessing.features import build_supervised_frame
from src.preprocessing.temporal import assert_purged_boundaries, temporal_split


def _frame(periods: int = 80) -> pd.DataFrame:
    stamps = pd.date_range("2026-09-01", periods=periods, freq="5min", tz="UTC")
    return pd.DataFrame(
        {
            "timestamp": stamps,
            "cpu_utilization": [float(index) for index in range(periods)],
            "origin": "simulated",
            "quality": "ok",
        }
    )


def test_features_never_use_future_cpu(config):
    supervised, features, _frequency, steps = build_supervised_frame(_frame(), config, "15m")
    assert steps == 3
    assert "target" not in features
    for name in features:
        assert "future" not in name
        assert not name.startswith("target")
    cpu = supervised.set_index("timestamp")["cpu_utilization"]
    for _, row in supervised.iterrows():
        target_time = row["target_timestamp"]
        if target_time in cpu.index:
            assert float(row["target"]) == pytest.approx(float(cpu.loc[target_time]))
        for name in features:
            if name.startswith("cpu_lag_"):
                lag = int(name.rsplit("_", maxsplit=1)[-1])
                source_time = row["prediction_time"] - pd.Timedelta(minutes=5 * lag)
                if source_time in cpu.index:
                    assert float(row[name]) == pytest.approx(float(cpu.loc[source_time]))


def test_split_is_chronological_and_purged(config):
    supervised, _features, _frequency, _steps = build_supervised_frame(_frame(90), config, "15m")
    train, validation, test = temporal_split(supervised, horizon="15m")
    assert train["timestamp"].max() < validation["timestamp"].min()
    assert validation["timestamp"].max() < test["timestamp"].min()
    assert_purged_boundaries(train, validation, test, "15m")


def test_or_true_is_not_used_to_hide_failures():
    with pytest.raises(LeakageError):
        from src.preprocessing.features import assert_no_future_features

        assert_no_future_features(["cpu_utilization", "cpu_future_15m"])
