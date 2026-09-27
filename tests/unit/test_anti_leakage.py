from __future__ import annotations

import json

import pandas as pd
import pytest

from src.exceptions import LeakageError
from src.inference.predict import predict
from src.preprocessing.features import (
    assert_no_future_features,
    assert_temporal_provenance,
    build_supervised_frame,
    feature_time_offsets,
)
from src.preprocessing.temporal import assert_purged_boundaries, parse_horizon, temporal_split


def _cpu_frame(periods: int = 48) -> pd.DataFrame:
    stamps = pd.date_range("2026-09-01", periods=periods, freq="5min", tz="UTC")
    return pd.DataFrame(
        {
            "timestamp": stamps,
            "cpu_utilization": [float(i) for i in range(periods)],
            "memory_utilization": [float(i) for i in range(periods)],
            "origin": "simulated",
            "quality": "ok",
        }
    )


def test_cpu_future_15m_is_rejected():
    with pytest.raises(LeakageError):
        assert_no_future_features(["cpu_utilization", "memory_utilization", "cpu_future_15m"])


def test_innocent_named_future_column_is_rejected(config):
    frame = _cpu_frame()
    frame["cpu_followup"] = frame["cpu_utilization"].shift(-1)
    leaked_config = json.loads(json.dumps(config))
    leaked_config["features"]["use_additional"] = True
    leaked_config["features"]["additional"] = ["memory_utilization", "cpu_followup"]
    with pytest.raises(LeakageError, match="cpu_followup"):
        build_supervised_frame(frame, leaked_config, "15m")


def test_each_row_has_feature_time_before_target(config):
    supervised, features, frequency, steps = build_supervised_frame(_cpu_frame(60), config, "15m")
    horizon = parse_horizon("15m")
    offsets = feature_time_offsets(features, frequency, config)
    assert steps == 3
    assert_temporal_provenance(supervised, features, offsets, "15m")

    for _, row in supervised.iterrows():
        prediction_time = pd.Timestamp(row["prediction_time"])
        target_time = pd.Timestamp(row["target_timestamp"])
        assert target_time == prediction_time + horizon
        for name in features:
            feature_time = prediction_time + offsets[name]
            assert feature_time <= prediction_time
        future = supervised.loc[supervised["timestamp"] == target_time, "cpu_utilization"]
        if not future.empty:
            assert float(row["target"]) == pytest.approx(float(future.iloc[0]))


def test_partition_boundaries_are_purged(config):
    supervised, _features, _frequency, _steps = build_supervised_frame(_cpu_frame(80), config, "15m")
    train, validation, test = temporal_split(supervised, horizon="15m")
    assert_purged_boundaries(train, validation, test, "15m")
    assert train["target_timestamp"].max() < validation["timestamp"].min()
    assert validation["target_timestamp"].max() < test["timestamp"].min()


def test_inference_rejects_future_feature(tmp_path):
    from src.models.baseline import PersistenceBaseline
    import joblib

    model = PersistenceBaseline().fit(pd.DataFrame({"cpu_utilization": [1.0]}), [1.0])
    bundle = {"model": model, "features": ["cpu_utilization", "cpu_future_15m"], "metadata": {}}
    joblib.dump(bundle, tmp_path / "model.joblib")
    (tmp_path / "metadata.json").write_text("{}", encoding="utf-8")
    with pytest.raises(LeakageError):
        predict({"cpu_utilization": 10, "cpu_future_15m": 99}, model_dir=tmp_path)
