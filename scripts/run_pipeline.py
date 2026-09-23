"""Full reproducible pipeline entry point."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.settings import load_config, resolve_path
from src.data.generate import write_simulated_dataset
from src.training.train import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
LOGGER = logging.getLogger("run_pipeline")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the complete ML pipeline")
    parser.add_argument("--config", default=None)
    parser.add_argument("--dataset", default=None)
    parser.add_argument("--skip-mlflow", action="store_true")
    args = parser.parse_args()

    config = load_config(args.config)
    dataset_path = Path(args.dataset) if args.dataset else resolve_path(config["paths"]["raw_data"])
    if not dataset_path.exists():
        LOGGER.info("Raw dataset missing; generating simulated fixture at %s", dataset_path)
        dataset_cfg = config.get("dataset", {})
        write_simulated_dataset(
            dataset_path,
            days=int(dataset_cfg.get("days", 3)),
            frequency_minutes=int(dataset_cfg.get("frequency_minutes", 5)),
            seed=int(dataset_cfg.get("seed", 42)),
            dataset_id=str(dataset_cfg.get("fixture_id", "dataset-sim-001")),
        )

    summary = run_pipeline(config_path=args.config, dataset_path=dataset_path, skip_mlflow=args.skip_mlflow)
    selected = summary["selected"]
    LOGGER.info(
        "Pipeline complete. selected=%s horizon=%s MAE=%.6f RMSE=%.6f sMAPE=%.6f",
        selected["model"],
        selected["horizon"],
        selected["mae"],
        selected["rmse"],
        selected["smape"],
    )
    print(json_summary(summary))
    return 0


def json_summary(summary: dict) -> str:
    import json

    payload = {
        "dataset_id": summary["dataset_id"],
        "data_kind": summary["data_kind"],
        "selected": {
            "model": summary["selected"]["model"],
            "horizon": summary["selected"]["horizon"],
            "mae": summary["selected"]["mae"],
            "rmse": summary["selected"]["rmse"],
            "smape": summary["selected"]["smape"],
            "latency_mean_ms": summary["selected"].get("latency_mean_ms"),
        },
        "mlflow": summary["mlflow"],
        "paths": summary["paths"],
    }
    return json.dumps(payload, indent=2, default=str)


if __name__ == "__main__":
    raise SystemExit(main())
