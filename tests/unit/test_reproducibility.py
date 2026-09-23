from __future__ import annotations

import numpy as np
import pandas as pd

from src.models.random_forest import RandomForestDemandModel
from src.models.xgboost_model import XGBoostDemandModel


def _data() -> tuple[pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(123)
    features = pd.DataFrame(
        {
            "cpu_utilization": rng.uniform(5, 90, size=50),
            "cpu_lag_1": rng.uniform(5, 90, size=50),
            "cpu_lag_2": rng.uniform(5, 90, size=50),
            "hour": rng.integers(0, 24, size=50),
        }
    )
    target = 0.7 * features["cpu_utilization"] + 0.2 * features["cpu_lag_1"] + 3
    return features, target


def test_random_forest_is_reproducible_with_same_seed():
    features, target = _data()
    first = RandomForestDemandModel(n_estimators=25, max_depth=5, random_state=42, n_jobs=1).fit(features, target)
    second = RandomForestDemandModel(n_estimators=25, max_depth=5, random_state=42, n_jobs=1).fit(features, target)
    np.testing.assert_allclose(first.predict(features), second.predict(features))


def test_xgboost_is_reproducible_with_same_seed():
    features, target = _data()
    first = XGBoostDemandModel(n_estimators=25, max_depth=3, random_state=42, n_jobs=1).fit(features, target)
    second = XGBoostDemandModel(n_estimators=25, max_depth=3, random_state=42, n_jobs=1).fit(features, target)
    np.testing.assert_allclose(first.predict(features), second.predict(features))
