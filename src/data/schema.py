"""Dataset contract aligned with Data Processing / informe.md."""

from __future__ import annotations

import re

SCHEMA_VERSION = "1.0"

REQUIRED_DATASET_FIELDS = (
    "schemaVersion",
    "datasetId",
    "period",
    "resource",
    "features",
    "origins",
    "dataStatus",
)

REQUIRED_METADATA_FIELDS = (
    "schemaVersion",
    "datasetId",
    "period",
    "resource",
    "origins",
    "dataStatus",
)

REQUIRED_PERIOD_FIELDS = ("start", "end")
REQUIRED_RESOURCE_FIELDS = ("type", "cluster", "id")
REQUIRED_RECORD_FIELDS = ("timestamp", "cpu_utilization", "origin", "quality")

OPTIONAL_RECORD_FIELDS = (
    "memory_utilization",
    "network_in",
    "network_out",
    "workload_count",
    "pod_count",
    "cpu_requests",
    "memory_requests",
)

ALLOWED_ORIGINS = frozenset({"observed", "simulated", "estimated", "unknown"})
ALLOWED_QUALITY = frozenset({"ok", "complete", "degraded", "warning"})
ALLOWED_DATA_STATUS = frozenset({"complete", "partial", "incomplete"})

TARGET_COLUMN = "cpu_utilization"
TARGET_UNIT = "%"
TIMESTAMP_COLUMN = "timestamp"
ORIGIN_COLUMN = "origin"
QUALITY_COLUMN = "quality"

FUTURE_FEATURE_PATTERN = re.compile(
    r"(future|lead|t_plus|ahead|^target$|^target_)",
    re.IGNORECASE,
)

FORBIDDEN_FEATURE_NAMES = frozenset(
    {
        "target",
        "cpu_future_5m",
        "cpu_future_15m",
        "cpu_future_30m",
    }
)
