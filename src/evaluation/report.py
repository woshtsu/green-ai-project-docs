"""Markdown report for a completed training run."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def write_model_report(
    path: Path,
    metadata: dict[str, Any],
    comparison: pd.DataFrame,
    selected: dict[str, Any],
    notes: list[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Model report — computational demand prediction",
        "",
        "This report is a **technical validation** of the ML pipeline.",
        "It is **not** an experimental production result and does **not** claim energy savings.",
        "",
        "## Dataset",
        "",
        f"- datasetId: `{metadata.get('datasetId')}`",
        f"- schemaVersion: `{metadata.get('schemaVersion')}`",
        f"- origins: `{metadata.get('origins')}`",
        f"- dataStatus: `{metadata.get('dataStatus')}`",
        f"- records used for selected horizon: `{selected.get('n_samples')}`",
        "",
        "## Selected model",
        "",
        f"- modelType: `{selected.get('model')}`",
        f"- horizon: `{selected.get('horizon')}`",
        f"- target: `cpu_utilization` (%)",
        f"- MAE: `{_fmt(selected.get('mae'))}`",
        f"- RMSE: `{_fmt(selected.get('rmse'))}`",
        f"- sMAPE: `{_fmt(selected.get('smape'))}`",
        f"- high-demand MAE: `{_fmt(selected.get('high_demand_mae'))}`",
        f"- mean latency (ms): `{_fmt(selected.get('latency_mean_ms'))}`",
        f"- p95 latency (ms): `{_fmt(selected.get('latency_p95_ms'))}`",
        "",
        "## Comparison",
        "",
        _table(comparison),
        "",
        "## Notes",
        "",
    ]
    for note in notes:
        lines.append(f"- {note}")
    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "- The default fixture is simulated (`origin=simulated`).",
            "- Metrics describe short-term CPU demand, not energy, kWh or CO2.",
            "- Feature importance is not causal.",
            "- Deep Learning was intentionally excluded from this version.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_No comparison rows._"
    display = frame.copy()
    keep = [col for col in ["model", "horizon", "mae", "rmse", "smape", "latency_mean_ms", "high_demand_mae"] if col in display.columns]
    display = display[keep]
    headers = list(display.columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for _, row in display.iterrows():
        cells = [_fmt(row[col]) if col != "model" and col != "horizon" else str(row[col]) for col in headers]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _fmt(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "n/a"
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)
