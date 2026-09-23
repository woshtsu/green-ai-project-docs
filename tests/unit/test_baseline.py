from __future__ import annotations

import pandas as pd
import pytest

from src.models.baseline import MovingAverageBaseline, PersistenceBaseline
from src.preprocessing.features import add_lags


def test_persistence_equals_current_cpu():
    features = pd.DataFrame({"cpu_utilization": [10.0, 25.5, 40.0]})
    model = PersistenceBaseline().fit(features, features["cpu_utilization"])
    predictions = model.predict(features)
    assert predictions.tolist() == [10.0, 25.5, 40.0]
    assert predictions.shape == (3,)


def test_moving_average_uses_current_and_lags():
    frame = pd.DataFrame({"cpu_utilization": [10.0, 20.0, 30.0, 40.0]})
    frame = add_lags(frame, lags=[1, 2])
    usable = frame.dropna()
    model = MovingAverageBaseline(window=3).fit(usable, usable["cpu_utilization"])
    predictions = model.predict(usable)
    expected = usable[["cpu_utilization", "cpu_lag_1", "cpu_lag_2"]].mean(axis=1).to_numpy()
    assert predictions == pytest.approx(expected)


def test_baselines_do_not_use_future_columns():
    features = pd.DataFrame(
        {
            "cpu_utilization": [10.0, 20.0],
            "cpu_lag_1": [9.0, 10.0],
        }
    )
    persistence = PersistenceBaseline().fit(features, [11.0, 21.0])
    moving = MovingAverageBaseline(window=2).fit(features, [11.0, 21.0])
    assert "cpu_future_15m" not in persistence.get_params().get("column", "")
    assert "cpu_future_15m" not in moving.get_params()["columns"]
    assert persistence.predict(features)[0] == 10.0
