"""External configuration loader."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load YAML configuration from disk and apply portable env overrides."""
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not config_path.is_absolute():
        config_path = PROJECT_ROOT / config_path
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError("Configuration root must be a mapping")
    _apply_env_overrides(data)
    return data


def _apply_env_overrides(data: dict[str, Any]) -> None:
    environment = os.getenv("ML_ENV")
    if environment:
        data["environment"] = environment
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI")
    if tracking_uri:
        data.setdefault("mlflow", {})["tracking_uri"] = tracking_uri
    model_dir = os.getenv("ML_MODEL_DIR")
    if model_dir:
        data.setdefault("paths", {})["models_selected"] = model_dir
    port = os.getenv("ML_PORT")
    if port:
        data.setdefault("service", {})["port"] = int(port)


@lru_cache(maxsize=4)
def get_settings(path: str | None = None) -> dict[str, Any]:
    return load_config(path)


def resolve_path(relative: str | Path) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute():
        return candidate
    return PROJECT_ROOT / candidate
