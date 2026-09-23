"""Plot generation for evaluation artifacts."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

sns.set_theme(style="whitegrid")


def write_evaluation_plots(
    timestamps: pd.Series,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    importance: pd.Series | None,
    output_dir: Path,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "actual_vs_predicted": str(output_dir / "actual_vs_predicted.png"),
        "error_distribution": str(output_dir / "error_distribution.png"),
        "temporal_prediction": str(output_dir / "temporal_prediction.png"),
        "feature_importance_plot": str(output_dir / "feature_importance.png"),
    }

    fig, axis = plt.subplots(figsize=(7, 5))
    axis.scatter(y_true, y_pred, alpha=0.6, edgecolor="none")
    limit = [min(y_true.min(), y_pred.min()), max(y_true.max(), y_pred.max())]
    axis.plot(limit, limit, color="black", linewidth=1)
    axis.set_xlabel("Observed CPU utilization (%)")
    axis.set_ylabel("Predicted CPU utilization (%)")
    axis.set_title("Observed vs predicted")
    fig.tight_layout()
    fig.savefig(paths["actual_vs_predicted"], dpi=120)
    plt.close(fig)

    errors = np.asarray(y_pred) - np.asarray(y_true)
    fig, axis = plt.subplots(figsize=(7, 5))
    sns.histplot(errors, bins=24, kde=True, ax=axis)
    axis.set_xlabel("Prediction error (predicted - observed)")
    axis.set_title("Error distribution")
    fig.tight_layout()
    fig.savefig(paths["error_distribution"], dpi=120)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(10, 4.5))
    axis.plot(timestamps, y_true, label="Observed")
    axis.plot(timestamps, y_pred, label="Predicted")
    axis.set_xlabel("Timestamp (UTC)")
    axis.set_ylabel("CPU utilization (%)")
    axis.set_title("Temporal prediction")
    axis.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(paths["temporal_prediction"], dpi=120)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(8, 5))
    if importance is not None and not importance.empty:
        top = importance.head(15)[::-1]
        axis.barh(top.index.astype(str), top.values)
        axis.set_xlabel("Relative importance")
        axis.set_title("Feature importance (not causal)")
    else:
        axis.text(0.5, 0.5, "Feature importance is not available for this model", ha="center", va="center")
        axis.set_axis_off()
        axis.set_title("Feature importance")
    fig.tight_layout()
    fig.savefig(paths["feature_importance_plot"], dpi=120)
    plt.close(fig)

    return paths
