from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.models.random_forest import RandomForestDemandModel
from src.models.xgboost_model import XGBoostDemandModel


def _toy() -> tuple[pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(42)
    features = pd.DataFrame(
        {
            "cpu_utilization": rng.uniform(10, 80, size=40),
            "cpu_lag_1": rng.uniform(10, 80, size=40),
            "hour": rng.integers(0, 24, size=40),
        }
    )
    target = features["cpu_utilization"] * 0.8 + 4
    return features, target


def test_random_forest_trains_and_predicts():
    features, target = _toy()
    model = RandomForestDemandModel(n_estimators=20, max_depth=4, random_state=42, n_jobs=1)
    model.fit(features, target)
    predictions = model.predict(features)
    assert predictions.shape == (40,)
    assert np.issubdtype(predictions.dtype, np.floating)
    assert not np.isnan(predictions).any()


def test_xgboost_trains_and_predicts():
    features, target = _toy()
    model = XGBoostDemandModel(n_estimators=20, max_depth=3, random_state=42, n_jobs=1)
    model.fit(features, target)
    predictions = model.predict(features)
    assert predictions.shape == (40,)
    assert np.issubdtype(predictions.dtype, np.floating)
    assert not np.isnan(predictions).any()


def test_models_respect_feature_order():
    features, target = _toy()
    model = RandomForestDemandModel(n_estimators=10, random_state=42, n_jobs=1)
    model.fit(features, target)
    shuffled = features[["hour", "cpu_lag_1", "cpu_utilization"]]
    left = model.predict(features)
    right = model.predict(shuffled)
    assert left == pytest.approx(right)
