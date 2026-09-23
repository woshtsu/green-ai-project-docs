"""Feature engineering with explicit anti-leakage guards."""

from __future__ import annotations

import logging
from typing import Any, Iterable

import pandas as pd

from src.data.schema import (
    FORBIDDEN_FEATURE_NAMES,
    FUTURE_FEATURE_PATTERN,
    ORIGIN_COLUMN,
    QUALITY_COLUMN,
    TARGET_COLUMN,
    TIMESTAMP_COLUMN,
)
from src.exceptions import InsufficientDataError, LeakageError, ValidationError
from src.preprocessing.temporal import assign_segments, horizon_steps, infer_frequency

LOGGER = logging.getLogger(__name__)

NON_FEATURE_COLUMNS = {
    TIMESTAMP_COLUMN,
    ORIGIN_COLUMN,
    QUALITY_COLUMN,
    "target",
    "_segment",
}


def assert_no_future_features(feature_names: Iterable[str]) -> None:
    """Fail if a future-looking feature name enters training or inference."""
    names = list(feature_names)
    for name in names:
        if name in FORBIDDEN_FEATURE_NAMES or name == "target":
            raise LeakageError(
                f"Forbidden future or target feature: {name}",
                details={"feature": name},
            )
        if FUTURE_FEATURE_PATTERN.search(str(name)):
            raise LeakageError(
                f"Feature name indicates future information: {name}",
                details={"feature": name},
            )


def add_temporal_features(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    stamps = pd.to_datetime(result[TIMESTAMP_COLUMN], utc=True)
    result["hour"] = stamps.dt.hour
    result["minute"] = stamps.dt.minute
    result["day_of_week"] = stamps.dt.dayofweek
    result["day_of_month"] = stamps.dt.day
    return result


def add_lags(
    frame: pd.DataFrame,
    column: str = TARGET_COLUMN,
    lags: Iterable[int] = (1, 2, 3),
    prefix: str = "cpu",
) -> pd.DataFrame:
    result = frame.copy()
    grouped = result.groupby("_segment", sort=False)[column] if "_segment" in result.columns else None
    for lag in lags:
        lag = int(lag)
        if lag < 1:
            raise LeakageError(
                f"Lag must be a positive past offset, received {lag}",
                details={"lag": lag},
            )
        name = f"{prefix}_lag_{lag}"
        if grouped is not None:
            result[name] = grouped.shift(lag)
        else:
            result[name] = result[column].shift(lag)
    return result


def add_rolling_features(
    frame: pd.DataFrame,
    column: str = TARGET_COLUMN,
    windows: Iterable[int] = (3, 6),
    stats: Iterable[str] = ("mean", "std", "min", "max"),
    primary_window: int = 6,
    prefix: str = "cpu",
) -> pd.DataFrame:
    """Rolling stats using information available at time t, never t+h."""
    result = frame.copy()
    source = result.groupby("_segment", sort=False)[column] if "_segment" in result.columns else result[column]

    for window in windows:
        window = int(window)
        if window < 2:
            raise ValidationError("Rolling window must be >= 2")
        rolled = source.rolling(window=window, min_periods=window)
        for stat in stats:
            series = _rolling_stat(rolled, stat)
            if "_segment" in result.columns:
                series = series.reset_index(level=0, drop=True)
            name = f"{prefix}_rolling_{stat}" if window == primary_window else f"{prefix}_rolling_{stat}_{window}"
            result[name] = series
    return result


def add_target(frame: pd.DataFrame, horizon: str, frequency: pd.Timedelta, column: str = TARGET_COLUMN) -> pd.DataFrame:
    steps = horizon_steps(horizon, frequency)
    result = frame.copy()
    if "_segment" in result.columns:
        result["target"] = result.groupby("_segment", sort=False)[column].shift(-steps)
    else:
        result["target"] = result[column].shift(-steps)
    result.attrs["horizon_steps"] = steps
    return result


def build_supervised_frame(
    frame: pd.DataFrame,
    config: dict[str, Any],
    horizon: str,
) -> tuple[pd.DataFrame, list[str], pd.Timedelta, int]:
    """Create a leakage-safe supervised table for one horizon."""
    if frame.empty:
        raise InsufficientDataError(
            "INSUFFICIENT_DATA: no rows for feature engineering",
            details={
                "code": "INSUFFICIENT_DATA",
                "available_records": 0,
                "period": None,
                "frequency": None,
                "horizon": horizon,
                "reason": "empty frame before features",
            },
        )

    frequency = infer_frequency(frame[TIMESTAMP_COLUMN])
    steps = horizon_steps(horizon, frequency)
    feature_cfg = config.get("features", {})

    working = assign_segments(frame, frequency)
    working = add_temporal_features(working)
    working = add_lags(
        working,
        column=TARGET_COLUMN,
        lags=feature_cfg.get("lags", [1, 2, 3]),
        prefix="cpu",
    )
    rolling_cfg = feature_cfg.get("rolling", {})
    working = add_rolling_features(
        working,
        column=TARGET_COLUMN,
        windows=rolling_cfg.get("windows", [3, 6]),
        stats=rolling_cfg.get("stats", ["mean", "std", "min", "max"]),
        primary_window=int(rolling_cfg.get("primary_window", 6)),
        prefix="cpu",
    )
    working = add_target(working, horizon=horizon, frequency=frequency)

    feature_names = select_feature_columns(working, config)
    assert_no_future_features(feature_names)
    if "target" in feature_names:
        raise LeakageError("Target column leaked into features")

    required = feature_names + ["target", TIMESTAMP_COLUMN]
    supervised = working.dropna(subset=required).reset_index(drop=True)
    if supervised.empty:
        raise InsufficientDataError(
            "INSUFFICIENT_DATA: no complete rows after feature and target generation",
            details={
                "code": "INSUFFICIENT_DATA",
                "available_records": int(len(working)),
                "period": {
                    "start": str(working[TIMESTAMP_COLUMN].min()) if not working.empty else None,
                    "end": str(working[TIMESTAMP_COLUMN].max()) if not working.empty else None,
                },
                "frequency": str(frequency),
                "horizon": horizon,
                "reason": "dropna removed every row (lags/rolling/target)",
            },
        )

    LOGGER.info(
        "Supervised frame horizon=%s freq=%s steps=%s rows=%s features=%s",
        horizon,
        frequency,
        steps,
        len(supervised),
        len(feature_names),
    )
    return supervised, feature_names, frequency, steps


def select_feature_columns(frame: pd.DataFrame, config: dict[str, Any]) -> list[str]:
    feature_cfg = config.get("features", {})
    names: list[str] = []

    if feature_cfg.get("include_current_target", True) and TARGET_COLUMN in frame.columns:
        names.append(TARGET_COLUMN)

    for column in feature_cfg.get("temporal", []):
        if column in frame.columns:
            names.append(column)

    for lag in feature_cfg.get("lags", []):
        name = f"cpu_lag_{int(lag)}"
        if name in frame.columns:
            names.append(name)

    rolling_cfg = feature_cfg.get("rolling", {})
    windows = [int(item) for item in rolling_cfg.get("windows", [])]
    primary = int(rolling_cfg.get("primary_window", windows[0] if windows else 6))
    for window in windows:
        for stat in rolling_cfg.get("stats", []):
            name = f"cpu_rolling_{stat}" if window == primary else f"cpu_rolling_{stat}_{window}"
            if name in frame.columns:
                names.append(name)

    for column in feature_cfg.get("additional", []):
        if column in frame.columns:
            names.append(column)

    unique: list[str] = []
    for name in names:
        if name not in unique and name not in NON_FEATURE_COLUMNS:
            unique.append(name)
    return unique


def _rolling_stat(rolled: pd.core.window.Rolling, stat: str) -> pd.Series:
    mapping = {
        "mean": rolled.mean,
        "std": rolled.std,
        "min": rolled.min,
        "max": rolled.max,
    }
    if stat not in mapping:
        raise ValidationError(f"Unsupported rolling statistic: {stat}")
    return mapping[stat]()
