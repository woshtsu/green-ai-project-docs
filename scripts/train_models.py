"""Train baseline, Random Forest and XGBoost, then select a model."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.training.train import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main() -> int:
    parser = argparse.ArgumentParser(description="Train demand-prediction models")
    parser.add_argument("--config", default=None)
    parser.add_argument("--dataset", default=None)
    parser.add_argument("--skip-mlflow", action="store_true")
    args = parser.parse_args()
    summary = run_pipeline(config_path=args.config, dataset_path=args.dataset, skip_mlflow=args.skip_mlflow)
    selected = summary["selected"]
    print(f"Selected {selected['model']} horizon={selected['horizon']} MAE={selected['mae']:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
