"""MLflow tracking and optional model registry."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Any

from src.config.settings import PROJECT_ROOT

LOGGER = logging.getLogger(__name__)


class MLflowTracker:
    def __init__(self, config: dict[str, Any]) -> None:
        mlflow_cfg = config.get("mlflow", {})
        self.enabled = True
        self.experiment_name = mlflow_cfg.get("experiment_name", "computational-demand-prediction")
        self.registered_model_name = mlflow_cfg.get("registered_model_name", "computational-demand-model")
        tracking_uri = mlflow_cfg.get("tracking_uri", "./mlruns")
        if not tracking_uri.startswith(("http://", "https://", "file:")):
            tracking_path = Path(tracking_uri)
            if not tracking_path.is_absolute():
                tracking_path = PROJECT_ROOT / tracking_path
            tracking_uri = tracking_path.resolve().as_uri()
        self.tracking_uri = tracking_uri
        self._mlflow = None
        try:
            import mlflow

            self._mlflow = mlflow
            mlflow.set_tracking_uri(self.tracking_uri)
            mlflow.set_experiment(self.experiment_name)
        except Exception as exc:  # pragma: no cover - environment-dependent
            LOGGER.warning("MLflow is unavailable: %s", exc)
            self.enabled = False

    def start_run(self, run_name: str) -> Any:
        if not self.enabled or self._mlflow is None:
            return _NullRun()
        return self._mlflow.start_run(run_name=run_name)

    def log_training_run(
        self,
        run,
        params: dict[str, Any],
        metrics: dict[str, Any],
        tags: dict[str, Any],
        artifacts: list[Path],
    ) -> str | None:
        if not self.enabled or self._mlflow is None:
            return None
        self._mlflow.log_params(_flatten_params(params))
        for key, value in metrics.items():
            if _is_number(value):
                self._mlflow.log_metric(key, float(value))
        self._mlflow.set_tags({key: "" if value is None else str(value) for key, value in tags.items()})
        for artifact in artifacts:
            if artifact.exists():
                self._mlflow.log_artifact(str(artifact))
        return run.info.run_id if run is not None else None

    def log_model_and_register(self, model: Any, artifact_path: str = "model") -> dict[str, Any]:
        result = {"run_id": None, "registered_version": None}
        if not self.enabled or self._mlflow is None:
            return result
        try:
            self._mlflow.sklearn.log_model(model, artifact_path=artifact_path)
        except Exception as exc:
            LOGGER.warning("Could not log sklearn model to MLflow: %s", exc)
            return result

        active = self._mlflow.active_run()
        if active is None:
            return result
        result["run_id"] = active.info.run_id
        model_uri = f"runs:/{active.info.run_id}/{artifact_path}"
        try:
            registered = self._mlflow.register_model(model_uri, self.registered_model_name)
            result["registered_version"] = getattr(registered, "version", None)
        except Exception as exc:
            LOGGER.warning("Model Registry registration failed: %s", exc)
        return result


def current_git_commit() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def current_environment(config: dict[str, Any]) -> str:
    return os.getenv("ML_ENV", str(config.get("environment", "experimental")))


def _flatten_params(params: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in params.items():
        name = f"{prefix}{key}" if not prefix else f"{prefix}.{key}" if prefix[-1] != "." else f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(_flatten_params(value, f"{name}."))
        elif isinstance(value, list):
            flat[name] = ",".join(str(item) for item in value)
        else:
            flat[name] = value
    return {key: str(value) for key, value in flat.items()}


def _is_number(value: Any) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return number == number  # NaN check


class _NullRun:
    def __enter__(self) -> "_NullRun":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    @property
    def info(self) -> Any:
        return type("Info", (), {"run_id": None})()
