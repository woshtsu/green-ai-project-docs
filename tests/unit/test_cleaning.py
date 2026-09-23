from __future__ import annotations

import pandas as pd
import pytest

from src.exceptions import ValidationError
from src.preprocessing.cleaning import clean_dataset


def test_missing_tokens_are_not_converted_to_zero():
    frame = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2026-09-01T00:00:00Z", "2026-09-01T00:05:00Z"], utc=True),
            "cpu_utilization": [12.0, 15.0],
            "memory_utilization": ["missing", "no_data"],
            "origin": ["simulated", "simulated"],
            "quality": ["ok", "ok"],
        }
    )
    cleaned = clean_dataset(frame)
    assert cleaned["memory_utilization"].isna().all()
    assert not (cleaned["memory_utilization"] == 0).any()


def test_naive_timestamps_are_not_localized_to_utc():
    frame = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2026-09-01T00:00:00", "2026-09-01T00:05:00"]),
            "cpu_utilization": [12.0, 15.0],
            "origin": ["simulated", "simulated"],
            "quality": ["ok", "ok"],
        }
    )
    with pytest.raises(ValidationError, match="timezone"):
        clean_dataset(frame)
