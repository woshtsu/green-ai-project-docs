"""Generate or copy a contract-compatible simulated dataset."""

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

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
LOGGER = logging.getLogger("prepare_dataset")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a simulated ML dataset fixture")
    parser.add_argument("--config", default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument("--days", type=int, default=None)
    args = parser.parse_args()

    config = load_config(args.config)
    dataset_cfg = config.get("dataset", {})
    output = Path(args.output) if args.output else resolve_path(config["paths"]["raw_data"])
    payload = write_simulated_dataset(
        output,
        days=args.days or int(dataset_cfg.get("days", 3)),
        frequency_minutes=int(dataset_cfg.get("frequency_minutes", 5)),
        seed=int(dataset_cfg.get("seed", 42)),
        dataset_id=str(dataset_cfg.get("fixture_id", "dataset-sim-001")),
    )
    LOGGER.info(
        "Wrote simulated dataset %s with %s records to %s",
        payload["datasetId"],
        len(payload["features"]),
        output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
