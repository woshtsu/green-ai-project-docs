"""Load versioned datasets produced by Data Processing (or fixtures)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from src.data.schema import TIMESTAMP_COLUMN
from src.data.validation import validate_payload
from src.exceptions import ValidationError

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class DatasetBundle:
    """In-memory dataset plus contract metadata."""

    frame: pd.DataFrame
    metadata: dict[str, Any]
    path: Path

    @property
    def dataset_id(self) -> str:
        return str(self.metadata.get("datasetId", "unknown"))

    @property
    def schema_version(self) -> str:
        return str(self.metadata.get("schemaVersion", "unknown"))


def load_dataset(path: str | Path) -> DatasetBundle:
    """Load a JSON dataset that follows the Data Processing contract."""
    dataset_path = Path(path)
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")

    with dataset_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        raise ValidationError("Dataset root must be a JSON object")
    validate_payload(payload)

    records = payload.get("features", [])
    if records is None:
        records = []
    if not isinstance(records, list):
        raise ValidationError("Dataset field 'features' must be a list")

    frame = pd.DataFrame(records)
    if TIMESTAMP_COLUMN in frame.columns:
        # Do not force UTC here: naive timestamps must fail validation.
        frame[TIMESTAMP_COLUMN] = pd.to_datetime(frame[TIMESTAMP_COLUMN], errors="coerce")

    metadata = {
        "schemaVersion": payload.get("schemaVersion"),
        "datasetId": payload.get("datasetId"),
        "period": payload.get("period"),
        "resource": payload.get("resource"),
        "origins": payload.get("origins"),
        "dataStatus": payload.get("dataStatus"),
        "warnings": payload.get("warnings") or [],
        "sourcePath": str(dataset_path),
        "feature_count": len(records),
    }
    LOGGER.info("Loaded dataset %s with %s records", metadata.get("datasetId"), len(frame))
    return DatasetBundle(frame=frame, metadata=metadata, path=dataset_path)
