"""Random Forest regressor wrapper."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from src.exceptions import ValidationError


class RandomForestDemandModel:
    name = "random_forest"
    complexity = 2

    def __init__(self, **params: Any) -> None:
        self.params = {
            "n_estimators": params.get("n_estimators", 80),
            "max_depth": params.get("max_depth", 8),
            "min_samples_split": params.get("min_samples_split", 4),
            "min_samples_leaf": params.get("min_samples_leaf", 2),
            "max_features": params.get("max_features", "sqrt"),
            "random_state": params.get("random_state", 42),
            "n_jobs": params.get("n_jobs", 1),
        }
        self.model = RandomForestRegressor(**self.params)
        self.feature_names: list[str] = []
        self.fitted = False

    def fit(self, features: pd.DataFrame, target: pd.Series | np.ndarray) -> "RandomForestDemandModel":
        if features.empty:
            raise ValidationError("Random Forest cannot train on an empty feature matrix")
        self.feature_names = list(features.columns)
        self.model.fit(features, target)
        self.fitted = True
        return self

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        if not self.fitted:
            raise ValidationError("Random Forest is not fitted")
        ordered = features[self.feature_names]
        predictions = np.asarray(self.model.predict(ordered), dtype=float)
        if np.isnan(predictions).any():
            raise ValidationError("Random Forest produced NaN predictions")
        return predictions

    def get_params(self) -> dict[str, Any]:
        return dict(self.params)

    def feature_importance(self) -> pd.Series | None:
        if not self.fitted:
            return None
        return pd.Series(self.model.feature_importances_, index=self.feature_names).sort_values(ascending=False)
