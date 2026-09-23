"""Evaluate the selected serialized model on the last test predictions."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.settings import load_config, resolve_path
from src.evaluation.metrics import mae, rmse, smape
from src.exceptions import ModelNotFoundError

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
LOGGER = logging.getLogger("evaluate_models")


def main() -> int:
    parser = argparse.ArgumentParser(description="Recompute metrics from saved test predictions")
    parser.add_argument("--config", default=None)
    args = parser.parse_args()
    config = load_config(args.config)
    pred_path = resolve_path(config["paths"]["results_dir"]) / "predictions" / "selected_model_predictions.csv"
    metrics_path = resolve_path(config["paths"]["results_dir"]) / "metrics" / "selected_model_metrics.json"
    if not pred_path.exists():
        raise ModelNotFoundError(f"Missing predictions artifact: {pred_path}")
    frame = pd.read_csv(pred_path)
    metrics = {
        "mae": mae(frame["y_true"], frame["y_pred"]),
        "rmse": rmse(frame["y_true"], frame["y_pred"]),
        "smape": smape(frame["y_true"], frame["y_pred"]),
        "n_samples": int(len(frame)),
    }
    LOGGER.info("Recomputed metrics: %s", metrics)
    if metrics_path.exists():
        stored = json.loads(metrics_path.read_text(encoding="utf-8"))
        LOGGER.info("Stored selected metrics: MAE=%s RMSE=%s sMAPE=%s", stored.get("mae"), stored.get("rmse"), stored.get("smape"))
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
