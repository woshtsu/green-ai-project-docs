"""Feature engineering with explicit anti-leakage guards."""

from __future__ import annotations

import logging
from typing import Any, Iterable

import numpy as np
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
from src.preprocessing.temporal import assign_segments, horizon_steps, infer_frequency, parse_horizon

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
    result["hour_sin"] = np.sin(2.0 * np.pi * result["hour"] / 24.0)
    result["hour_cos"] = np.cos(2.0 * np.pi * result["hour"] / 24.0)
    result["dow_sin"] = np.sin(2.0 * np.pi * result["day_of_week"] / 7.0)
    result["dow_cos"] = np.cos(2.0 * np.pi * result["day_of_week"] / 7.0)
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
    require_target: bool = True,
) -> tuple[pd.DataFrame, list[str], pd.Timedelta, int]:
    """Create a leakage-safe supervised table for one horizon.

    Training uses require_target=True so incomplete future rows are dropped.
    Inference uses require_target=False so the latest complete feature row
    can forecast prediction_time + horizon.
    """
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
    working["prediction_time"] = pd.to_datetime(working[TIMESTAMP_COLUMN], utc=True)
    working["target_timestamp"] = working["prediction_time"] + parse_horizon(horizon)

    feature_names = select_feature_columns(working, config)
    assert_no_future_features(feature_names)
    if "target" in feature_names:
        raise LeakageError("Target column leaked into features")
    offsets = feature_time_offsets(feature_names, frequency, config)
    assert_no_positive_offsets(offsets)
    assert_features_not_copied_from_future(working, feature_names, steps)

    required = feature_names + [TIMESTAMP_COLUMN, "prediction_time", "target_timestamp"]
    if require_target:
        required = required + ["target"]
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

    if require_target:
        assert_temporal_provenance(supervised, feature_names, offsets, horizon)
    LOGGER.info(
        "Supervised frame horizon=%s freq=%s steps=%s rows=%s features=%s",
        horizon,
        frequency,
        steps,
        len(supervised),
        len(feature_names),
    )
    return supervised, feature_names, frequency, steps


def feature_time_offsets(
    feature_names: Iterable[str],
    frequency: pd.Timedelta,
    config: dict[str, Any] | None = None,
) -> dict[str, pd.Timedelta]:
    """Newest information used by each feature, relative to prediction_time."""
    _ = config
    offsets: dict[str, pd.Timedelta] = {}
    for name in feature_names:
        if name.startswith("cpu_lag_"):
            lag = int(str(name).rsplit("_", maxsplit=1)[-1])
            offsets[name] = -lag * frequency
        else:
            offsets[name] = pd.Timedelta(0)
    return offsets


def assert_no_positive_offsets(offsets: dict[str, pd.Timedelta]) -> None:
    leaked = {name: str(delta) for name, delta in offsets.items() if delta > pd.Timedelta(0)}
    if leaked:
        raise LeakageError(
            "Features use information after prediction_time",
            details={"features": leaked},
        )


def assert_temporal_provenance(
    frame: pd.DataFrame,
    feature_names: Iterable[str],
    offsets: dict[str, pd.Timedelta],
    horizon: str,
) -> None:
    """For every row: feature_time <= prediction_time and target_time = prediction_time + horizon."""
    if frame.empty:
        raise LeakageError("Cannot verify provenance on an empty frame")
    prediction_time = pd.to_datetime(frame["prediction_time"], utc=True)
    expected_target = prediction_time + parse_horizon(horizon)
    actual_target = pd.to_datetime(frame["target_timestamp"], utc=True)
    if not actual_target.equals(expected_target):
        raise LeakageError("target_timestamp is not prediction_time + horizon")

    for name in feature_names:
        feature_time = prediction_time + offsets[name]
        if (feature_time > prediction_time).any():
            raise LeakageError(
                f"Feature {name} timestamp is after prediction_time",
                details={"feature": name},
            )

    cpu_by_time = frame.set_index(TIMESTAMP_COLUMN)[TARGET_COLUMN]
    for idx, row in frame.iterrows():
        target_time = row["target_timestamp"]
        if target_time in cpu_by_time.index:
            observed = float(cpu_by_time.loc[target_time] if not isinstance(cpu_by_time.loc[target_time], pd.Series) else cpu_by_time.loc[target_time].iloc[0])
            if not math_isclose(float(row["target"]), observed):
                raise LeakageError(
                    "Target value does not match CPU at prediction_time + horizon",
                    details={"row": int(idx) if isinstance(idx, (int, float)) else str(idx)},
                )


def assert_features_not_copied_from_future(
    frame: pd.DataFrame,
    feature_names: Iterable[str],
    max_lead_steps: int,
) -> None:
    """Reject features that exactly copy CPU(t+k), even with an innocent name."""
    if TARGET_COLUMN not in frame.columns:
        return
    cpu = pd.to_numeric(frame[TARGET_COLUMN], errors="coerce")
    for name in feature_names:
        if name == TARGET_COLUMN:
            continue
        series = pd.to_numeric(frame[name], errors="coerce")
        if series.nunique(dropna=True) < 3:
            continue
        for lead in range(1, max(max_lead_steps, 1) + 1):
            future = cpu.shift(-lead)
            mask = series.notna() & future.notna()
            if int(mask.sum()) < 8:
                continue
            if (series[mask].to_numpy() == future[mask].to_numpy()).all():
                raise LeakageError(
                    f"Feature '{name}' copies CPU(t+{lead}) despite its name",
                    details={"feature": name, "lead_steps": lead},
                )


def math_isclose(left: float, right: float, tolerance: float = 1e-9) -> bool:
    return abs(left - right) <= tolerance


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

    if feature_cfg.get("use_additional", False):
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
