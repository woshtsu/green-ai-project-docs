"""Persistence and moving-average baselines."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.data.schema import TARGET_COLUMN
from src.exceptions import ValidationError


class PersistenceBaseline:
    """ŷ(t+h) = y(t)."""

    name = "persistence"
    complexity = 0

    def __init__(self, column: str = TARGET_COLUMN) -> None:
        self.column = column
        self.fitted = False

    def fit(self, features: pd.DataFrame, target: pd.Series | np.ndarray) -> "PersistenceBaseline":
        if self.column not in features.columns:
            raise ValidationError(f"Persistence baseline requires '{self.column}'")
        self.fitted = True
        return self

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        if not self.fitted:
            raise ValidationError("Persistence baseline is not fitted")
        if self.column not in features.columns:
            raise ValidationError(f"Missing column '{self.column}' for persistence")
        values = pd.to_numeric(features[self.column], errors="coerce").to_numpy(dtype=float)
        if np.isnan(values).any():
            raise ValidationError("Persistence predictions contain NaN")
        return values

    def get_params(self) -> dict[str, Any]:
        return {"column": self.column, "rule": "y_hat(t+h) = y(t)"}

    def feature_importance(self) -> pd.Series | None:
        return None


class MovingAverageBaseline:
    """ŷ(t+h) = mean(y(t), y(t-1), ..., y(t-window+1))."""

    name = "moving_average"
    complexity = 1

    def __init__(self, window: int = 3, column: str = TARGET_COLUMN) -> None:
        if window < 1:
            raise ValidationError("Moving average window must be >= 1")
        self.window = window
        self.column = column
        self.fitted = False
        self._columns: list[str] = []

    def fit(self, features: pd.DataFrame, target: pd.Series | np.ndarray) -> "MovingAverageBaseline":
        self._columns = self._resolve_columns(features)
        if not self._columns:
            raise ValidationError("Moving average baseline has no available CPU columns")
        self.fitted = True
        return self

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        if not self.fitted:
            raise ValidationError("Moving average baseline is not fitted")
        missing = [column for column in self._columns if column not in features.columns]
        if missing:
            raise ValidationError(f"Missing columns for moving average: {missing}")
        values = features[self._columns].apply(pd.to_numeric, errors="coerce")
        predictions = values.mean(axis=1).to_numpy(dtype=float)
        if np.isnan(predictions).any():
            raise ValidationError("Moving average predictions contain NaN")
        return predictions

    def get_params(self) -> dict[str, Any]:
        return {"window": self.window, "columns": self._columns}

    def feature_importance(self) -> pd.Series | None:
        return None

    def _resolve_columns(self, features: pd.DataFrame) -> list[str]:
        columns = [self.column]
        for lag in range(1, self.window):
            candidate = f"cpu_lag_{lag}"
            if candidate in features.columns:
                columns.append(candidate)
        return [column for column in columns if column in features.columns]
