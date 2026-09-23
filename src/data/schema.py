"""Dataset contract aligned with Data Processing / informe.md."""

from __future__ import annotations

import re

SCHEMA_VERSION = "1.0"
SUPPORTED_SCHEMA_VERSIONS = frozenset({SCHEMA_VERSION})

GRANULARITY = "one_resource_per_dataset"
EXPECTED_FREQUENCY = "5m"
GAP_TOLERANCE_MULTIPLIER = 1.5
MIN_WINDOW_BY_HORIZON = {"5m": 12, "15m": 24, "30m": 36}

COLUMN_SPEC: dict[str, dict[str, str]] = {
    "timestamp": {"type": "datetime", "unit": "RFC3339"},
    "cpu_utilization": {"type": "float", "unit": "%"},
    "memory_utilization": {"type": "float", "unit": "%"},
    "network_in": {"type": "float", "unit": "bytes/s"},
    "network_out": {"type": "float", "unit": "bytes/s"},
    "workload_count": {"type": "integer", "unit": "count"},
    "pod_count": {"type": "integer", "unit": "count"},
    "cpu_requests": {"type": "float", "unit": "cores"},
    "memory_requests": {"type": "float", "unit": "MiB"},
    "origin": {"type": "string", "unit": "enum"},
    "quality": {"type": "string", "unit": "enum"},
}

MONITORING_CONVERSIONS = {
    "cpu_utilization": "Monitoring delivers CPU as a ratio in [0, 1]. Multiply by 100 before this contract.",
    "memory_utilization": "Monitoring delivers memory in bytes. Convert to percent of allocatable memory before this contract.",
}

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
