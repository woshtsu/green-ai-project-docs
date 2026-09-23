"""Deterministic simulated dataset generator.

Generated records always carry origin = simulated and must never be
presented as real observations.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np

from src.data.schema import SCHEMA_VERSION


def generate_simulated_dataset(
    start: datetime | None = None,
    days: int = 3,
    frequency_minutes: int = 5,
    seed: int = 42,
    dataset_id: str = "dataset-sim-001",
    cluster: str = "cluster-01",
    node_id: str = "node-01",
) -> dict[str, Any]:
    """Build a contract-compatible dataset with a daily CPU pattern."""
    if start is None:
        start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)

    rng = np.random.default_rng(seed)
    steps = int((days * 24 * 60) / frequency_minutes)
    records: list[dict[str, Any]] = []

    for index in range(steps):
        timestamp = start + timedelta(minutes=frequency_minutes * index)
        hour = timestamp.hour + timestamp.minute / 60.0
        weekday = timestamp.weekday()

        daily = 28.0 + 32.0 * (0.5 + 0.5 * np.sin((hour - 8.5) / 24.0 * 2.0 * np.pi))
        weekly = -8.0 if weekday >= 5 else 0.0
        noise = float(rng.normal(0.0, 3.5))
        spike = 18.0 if rng.random() < 0.03 else 0.0
        cpu = float(np.clip(daily + weekly + noise + spike, 4.0, 98.0))

        memory = float(np.clip(45.0 + 0.35 * cpu + rng.normal(0.0, 4.0), 15.0, 95.0))
        network_in = float(np.clip(400.0 + 25.0 * cpu + rng.normal(0.0, 80.0), 50.0, 8000.0))
        network_out = float(np.clip(250.0 + 18.0 * cpu + rng.normal(0.0, 60.0), 30.0, 6000.0))
        workload_count = int(np.clip(round(4 + cpu / 12 + rng.normal(0.0, 1.0)), 1, 24))
        pod_count = int(np.clip(workload_count * 2 + rng.integers(-1, 3), 2, 48))

        records.append(
            {
                "timestamp": timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "cpu_utilization": round(cpu, 4),
                "memory_utilization": round(memory, 4),
                "network_in": round(network_in, 4),
                "network_out": round(network_out, 4),
                "workload_count": workload_count,
                "pod_count": pod_count,
                "cpu_requests": 4.0,
                "memory_requests": 8192.0,
                "origin": "simulated",
                "quality": "ok",
            }
        )

    end = start + timedelta(minutes=frequency_minutes * (steps - 1))
    return {
        "schemaVersion": SCHEMA_VERSION,
        "datasetId": dataset_id,
        "period": {
            "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "resource": {
            "type": "node",
            "cluster": cluster,
            "id": node_id,
        },
        "features": records,
        "origins": ["simulated"],
        "dataStatus": "complete",
        "warnings": [
            "Dataset generated for technical validation. origin=simulated. Not real observations."
        ],
    }


def write_simulated_dataset(path: str | Path, **kwargs: Any) -> dict[str, Any]:
    payload = generate_simulated_dataset(**kwargs)
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return payload
