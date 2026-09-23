from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.config.settings import PROJECT_ROOT, load_config
from src.data.generate import generate_simulated_dataset, write_simulated_dataset

FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "sample_dataset.json"


@pytest.fixture(scope="session")
def sample_dataset_path() -> Path:
    if not FIXTURE_PATH.exists():
        write_simulated_dataset(
            FIXTURE_PATH,
            days=1,
            frequency_minutes=5,
            seed=42,
            dataset_id="dataset-test-001",
        )
    return FIXTURE_PATH


@pytest.fixture
def sample_payload(sample_dataset_path: Path) -> dict:
    return json.loads(sample_dataset_path.read_text(encoding="utf-8"))


@pytest.fixture
def sample_frame(sample_payload: dict) -> pd.DataFrame:
    frame = pd.DataFrame(sample_payload["features"])
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    return frame


@pytest.fixture
def config() -> dict:
    return load_config()


@pytest.fixture
def compact_payload() -> dict:
    return generate_simulated_dataset(
        days=1,
        frequency_minutes=5,
        seed=7,
        dataset_id="dataset-compact-001",
    )
