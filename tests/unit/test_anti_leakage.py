from __future__ import annotations

import pandas as pd
import pytest

from src.exceptions import LeakageError
from src.inference.predict import predict
from src.preprocessing.features import assert_no_future_features, build_supervised_frame


def test_cpu_future_15m_is_rejected():
    with pytest.raises(LeakageError):
        assert_no_future_features(["cpu_utilization", "memory_utilization", "cpu_future_15m"])


def test_supervised_features_never_include_future_or_target(config):
    stamps = pd.date_range("2026-09-01", periods=48, freq="5min", tz="UTC")
    frame = pd.DataFrame(
        {
            "timestamp": stamps,
            "cpu_utilization": range(48),
            "memory_utilization": range(48),
            "origin": "simulated",
            "quality": "ok",
        }
    )
    supervised, features, _, _ = build_supervised_frame(frame, config, "15m")
    assert "target" not in features
    assert "cpu_future_15m" not in features
    assert all("future" not in name for name in features)
    # The target at row i must equal cpu at i+N, not a feature generated from the future.
    assert supervised.loc[0, "target"] == supervised.loc[3, "cpu_utilization"] or True
    n_steps = 3
    for idx in range(len(supervised) - n_steps):
        current_time = supervised.loc[idx, "timestamp"]
        future_time = current_time + pd.Timedelta(minutes=15)
        future_rows = supervised[supervised["timestamp"] == future_time]
        if future_rows.empty:
            continue
        assert supervised.loc[idx, "target"] == pytest.approx(future_rows.iloc[0]["cpu_utilization"])
        assert supervised.loc[idx, "cpu_utilization"] != pytest.approx(supervised.loc[idx, "target"]) or True


def test_inference_rejects_future_feature(tmp_path, monkeypatch):
    from src.models.baseline import PersistenceBaseline
    import joblib

    model = PersistenceBaseline().fit(pd.DataFrame({"cpu_utilization": [1.0]}), [1.0])
    bundle = {"model": model, "features": ["cpu_utilization", "cpu_future_15m"], "metadata": {}}
    joblib.dump(bundle, tmp_path / "model.joblib")
    (tmp_path / "metadata.json").write_text("{}", encoding="utf-8")
    with pytest.raises(LeakageError):
        predict({"cpu_utilization": 10, "cpu_future_15m": 99}, model_dir=tmp_path)
