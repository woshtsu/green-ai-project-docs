"""XGBoost regressor wrapper."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from src.exceptions import ValidationError


class XGBoostDemandModel:
    name = "xgboost"
    complexity = 3

    def __init__(self, **params: Any) -> None:
        self.params = {
            "n_estimators": params.get("n_estimators", 80),
            "max_depth": params.get("max_depth", 4),
            "learning_rate": params.get("learning_rate", 0.1),
            "subsample": params.get("subsample", 0.8),
            "colsample_bytree": params.get("colsample_bytree", 0.8),
            "objective": params.get("objective", "reg:squarederror"),
            "random_state": params.get("random_state", 42),
            "n_jobs": params.get("n_jobs", 1),
            "verbosity": params.get("verbosity", 0),
        }
        self.model = XGBRegressor(**self.params)
        self.feature_names: list[str] = []
        self.fitted = False

    def fit(self, features: pd.DataFrame, target: pd.Series | np.ndarray) -> "XGBoostDemandModel":
        if features.empty:
            raise ValidationError("XGBoost cannot train on an empty feature matrix")
        self.feature_names = list(features.columns)
        self.model.fit(features, target)
        self.fitted = True
        return self

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        if not self.fitted:
            raise ValidationError("XGBoost is not fitted")
        ordered = features[self.feature_names]
        predictions = np.asarray(self.model.predict(ordered), dtype=float)
        if np.isnan(predictions).any():
            raise ValidationError("XGBoost produced NaN predictions")
        return predictions

    def get_params(self) -> dict[str, Any]:
        return dict(self.params)

    def feature_importance(self) -> pd.Series | None:
        if not self.fitted:
            return None
        booster_scores = self.model.feature_importances_
        return pd.Series(booster_scores, index=self.feature_names).sort_values(ascending=False)
