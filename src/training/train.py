"""End-to-end training pipeline."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from src.config.settings import load_config, resolve_path
from src.data.loader import DatasetBundle, load_dataset
from src.data.schema import TARGET_COLUMN, TIMESTAMP_COLUMN
from src.data.validation import validate_dataset
from src.evaluation.comparison import comparison_frame, select_model
from src.evaluation.evaluation import evaluate_predictions
from src.evaluation.plots import write_evaluation_plots
from src.evaluation.report import write_model_report
from src.exceptions import InsufficientDataError, ValidationError
from src.mlflow.tracking import MLflowTracker, current_environment, current_git_commit
from src.models.baseline import MovingAverageBaseline, PersistenceBaseline
from src.models.random_forest import RandomForestDemandModel
from src.models.xgboost_model import XGBoostDemandModel
from src.preprocessing.cleaning import clean_dataset
from src.preprocessing.features import build_supervised_frame
from src.preprocessing.temporal import assert_purged_boundaries, temporal_split
from src.reproducibility import sha256_file, sha256_json, write_manifest

LOGGER = logging.getLogger(__name__)


def run_pipeline(
    config_path: str | Path | None = None,
    dataset_path: str | Path | None = None,
    skip_mlflow: bool = False,
) -> dict[str, Any]:
    """Execute load → validate → features → models → selection → artifacts."""
    config = load_config(config_path)
    bundle = _load(config, dataset_path)
    report = validate_dataset(
        bundle.frame,
        bundle.metadata,
        allow_mixed_origins=bool(config.get("data", {}).get("allow_mixed_origins", False)),
    )
    cleaned = clean_dataset(bundle.frame)

    processed_dir = resolve_path(config["paths"]["processed_dir"])
    processed_dir.mkdir(parents=True, exist_ok=True)
    cleaned_path = processed_dir / "cleaned.csv"
    cleaned.to_csv(cleaned_path, index=False)

    rows: list[dict[str, Any]] = []
    artifacts_by_key: dict[str, dict[str, Any]] = {}
    notes = [
        "Results come from a technical pipeline run.",
        f"Dataset origin metadata: {bundle.metadata.get('origins')}.",
        "Do not interpret these metrics as production accuracy or energy savings.",
    ]

    for horizon in config.get("horizons", ["15m"]):
        supervised, feature_names, frequency, steps = build_supervised_frame(cleaned, config, horizon)
        _assert_enough_rows(supervised, bundle, frequency, horizon, int(config.get("min_train_samples", 20)))
        train, validation, test = temporal_split(
            supervised,
            train_ratio=float(config["split"]["train_ratio"]),
            validation_ratio=float(config["split"]["validation_ratio"]),
            test_ratio=float(config["split"]["test_ratio"]),
            horizon=horizon,
        )
        assert_purged_boundaries(train, validation, test, horizon)
        if len(train) < int(config.get("min_train_samples", 20)):
            raise InsufficientDataError(
                "INSUFFICIENT_DATA: training partition is too small",
                details=_insufficient_details(supervised, bundle, frequency, horizon, "training partition too small"),
            )
        if len(validation) < int(config.get("min_eval_samples", 5)) or len(test) < int(config.get("min_eval_samples", 5)):
            raise InsufficientDataError(
                "INSUFFICIENT_DATA: validation or test partition is too small",
                details=_insufficient_details(supervised, bundle, frequency, horizon, "eval partition too small"),
            )

        x_train, y_train = _xy(train, feature_names)
        x_valid, y_valid = _xy(validation, feature_names)
        x_test, y_test = _xy(test, feature_names)

        models = _build_models(config)
        for model in models:
            LOGGER.info("Fitting %s on TRAIN for horizon=%s", model.name, horizon)
            model.fit(x_train, y_train)
            validation_pred = model.predict(x_valid)
            val_metrics = evaluate_predictions(
                y_valid,
                validation_pred,
                config=config,
                predict_fn=lambda current=model, data=x_valid: current.predict(data),
                repeats=int(config.get("latency_repeats", 5)),
            )
            row = {
                "model": model.name,
                "horizon": horizon,
                "split": "validation",
                "features": feature_names,
                "frequency": str(frequency),
                "horizon_steps": steps,
                **val_metrics,
            }
            rows.append(row)
            artifacts_by_key[f"{model.name}:{horizon}"] = {
                "candidate": model,
                "feature_names": feature_names,
                "x_train": x_train,
                "y_train": y_train,
                "x_valid": x_valid,
                "y_valid": y_valid,
                "x_test": x_test,
                "y_test": y_test,
                "validation_predictions": validation_pred,
                "timestamps": test[TIMESTAMP_COLUMN],
                "validation_metrics": val_metrics,
                "frequency": frequency,
                "steps": steps,
                "train_frame": train,
                "validation_frame": validation,
                "test_frame": test,
            }
            _write_candidate(config, model, horizon, feature_names, bundle, val_metrics)

    if not rows:
        raise ValidationError("No models were evaluated")

    comparison = comparison_frame(rows)
    selected_horizon = str(config.get("default_horizon", "15m"))
    selected = select_model(
        rows,
        horizon=selected_horizon,
        equivalence_mae_relative=float(config.get("equivalence_mae_relative", 0.02)),
    )
    selected_key = f"{selected['model']}:{selected['horizon']}"
    selected_artifacts = artifacts_by_key[selected_key]
    final_model = _retrain_selected(config, selected["model"], selected_artifacts)
    test_predictions = final_model.predict(selected_artifacts["x_test"])
    test_metrics = evaluate_predictions(
        selected_artifacts["y_test"],
        test_predictions,
        config=config,
        predict_fn=lambda current=final_model, data=selected_artifacts["x_test"]: current.predict(data),
        repeats=int(config.get("latency_repeats", 5)),
    )
    selected_artifacts["model"] = final_model
    selected_artifacts["predictions"] = test_predictions
    selected_artifacts["test_metrics"] = test_metrics
    selected["validation_metrics"] = selected_artifacts["validation_metrics"]
    selected["test_metrics"] = test_metrics
    selected["mae"] = test_metrics["mae"]
    selected["rmse"] = test_metrics["rmse"]
    selected["smape"] = test_metrics["smape"]
    selected["latency_mean_ms"] = test_metrics.get("latency_mean_ms")
    selected["latency_p95_ms"] = test_metrics.get("latency_p95_ms")
    selected["high_demand_mae"] = test_metrics.get("high_demand_mae")
    selected["high_demand_rmse"] = test_metrics.get("high_demand_rmse")
    selected["split_used_for_selection"] = "validation"
    selected["split_used_for_reported_metrics"] = "test"

    result_paths = _write_outputs(
        config=config,
        bundle=bundle,
        comparison=comparison,
        selected=selected,
        selected_artifacts=selected_artifacts,
        notes=notes,
        validation_report=report,
    )

    mlflow_info = {"run_id": None, "experiment": None, "model_version": None}
    if not skip_mlflow:
        mlflow_info = _log_mlflow(config, bundle, selected, selected_artifacts, result_paths)

    summary = {
        "dataset_id": bundle.dataset_id,
        "selected": selected,
        "comparison": rows,
        "paths": result_paths,
        "mlflow": mlflow_info,
        "validation": report,
        "data_kind": "technical_simulated" if "simulated" in (bundle.metadata.get("origins") or []) else "provided",
    }
    LOGGER.info("Selected %s for horizon %s", selected["model"], selected["horizon"])
    return summary


def _load(config: dict[str, Any], dataset_path: str | Path | None) -> DatasetBundle:
    path = Path(dataset_path) if dataset_path else resolve_path(config["paths"]["raw_data"])
    return load_dataset(path)


def _retrain_selected(config: dict[str, Any], model_name: str, artifacts: dict[str, Any]) -> Any:
    """Retrain the selected model on TRAIN+VALIDATION after selection, never on TEST."""
    x_fit = pd.concat([artifacts["x_train"], artifacts["x_valid"]], axis=0)
    y_fit = pd.concat([artifacts["y_train"], artifacts["y_valid"]], axis=0)
    final = next(model for model in _build_models(config) if model.name == model_name)
    LOGGER.info("Retraining selected %s on TRAIN+VALIDATION", model_name)
    final.fit(x_fit, y_fit)
    return final


def _build_models(config: dict[str, Any]) -> list[Any]:
    rf = dict(config.get("random_forest", {}))
    xgb = dict(config.get("xgboost", {}))
    window = int(config.get("baseline", {}).get("moving_average_window", 3))
    return [
        PersistenceBaseline(),
        MovingAverageBaseline(window=window),
        RandomForestDemandModel(**rf),
        XGBoostDemandModel(**xgb),
    ]


def _xy(frame: pd.DataFrame, feature_names: list[str]) -> tuple[pd.DataFrame, pd.Series]:
    return frame[feature_names].copy(), frame["target"].astype(float).copy()


def _assert_enough_rows(
    frame: pd.DataFrame,
    bundle: DatasetBundle,
    frequency: pd.Timedelta,
    horizon: str,
    minimum: int,
) -> None:
    if len(frame) < minimum:
        raise InsufficientDataError(
            "INSUFFICIENT_DATA: supervised dataset is too small",
            details=_insufficient_details(frame, bundle, frequency, horizon, "not enough complete supervised rows"),
        )


def _insufficient_details(
    frame: pd.DataFrame,
    bundle: DatasetBundle,
    frequency: pd.Timedelta | None,
    horizon: str,
    reason: str,
) -> dict[str, Any]:
    period = bundle.metadata.get("period")
    if TIMESTAMP_COLUMN in frame.columns and not frame.empty:
        period = {"start": str(frame[TIMESTAMP_COLUMN].min()), "end": str(frame[TIMESTAMP_COLUMN].max())}
    return {
        "code": "INSUFFICIENT_DATA",
        "available_records": int(len(frame)),
        "period": period,
        "frequency": str(frequency) if frequency is not None else None,
        "horizon": horizon,
        "reason": reason,
    }


def _write_candidate(
    config: dict[str, Any],
    model: Any,
    horizon: str,
    feature_names: list[str],
    bundle: DatasetBundle,
    metrics: dict[str, Any],
) -> None:
    directory = resolve_path(config["paths"]["models_candidate"])
    directory.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": model,
        "features": feature_names,
        "horizon": horizon,
        "datasetId": bundle.dataset_id,
    }
    joblib.dump(payload, directory / f"{model.name}_{horizon}.joblib")
    (directory / f"{model.name}_{horizon}.json").write_text(
        json.dumps({"model": model.name, "horizon": horizon, "metrics": _jsonable(metrics)}, indent=2),
        encoding="utf-8",
    )


def _write_outputs(
    config: dict[str, Any],
    bundle: DatasetBundle,
    comparison: pd.DataFrame,
    selected: dict[str, Any],
    selected_artifacts: dict[str, Any],
    notes: list[str],
    validation_report: dict[str, Any],
) -> dict[str, str]:
    results_dir = resolve_path(config["paths"]["results_dir"])
    metrics_dir = results_dir / "metrics"
    pred_dir = results_dir / "predictions"
    plots_dir = results_dir / "plots"
    reports_dir = results_dir / "reports"
    selected_dir = resolve_path(config["paths"]["models_selected"])
    for directory in (metrics_dir, pred_dir, plots_dir, reports_dir, selected_dir):
        directory.mkdir(parents=True, exist_ok=True)

    comparison_path = metrics_dir / "model_comparison.csv"
    comparison.to_csv(comparison_path, index=False)
    validation_comparison_path = metrics_dir / "validation_comparison.csv"
    comparison.to_csv(validation_comparison_path, index=False)

    selected_metrics_path = metrics_dir / "selected_model_metrics.json"
    selected_metrics_path.write_text(json.dumps(_jsonable(selected), indent=2), encoding="utf-8")
    validation_metrics_path = metrics_dir / "selected_validation_metrics.json"
    validation_metrics_path.write_text(
        json.dumps(_jsonable(selected_artifacts.get("validation_metrics") or {}), indent=2),
        encoding="utf-8",
    )
    test_metrics_path = metrics_dir / "selected_test_metrics.json"
    test_metrics_path.write_text(
        json.dumps(_jsonable(selected_artifacts.get("test_metrics") or selected), indent=2),
        encoding="utf-8",
    )

    predictions = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(selected_artifacts["timestamps"], utc=True),
            "y_true": selected_artifacts["y_test"].to_numpy(),
            "y_pred": selected_artifacts["predictions"],
            "error": selected_artifacts["predictions"] - selected_artifacts["y_test"].to_numpy(),
            "model": selected["model"],
            "horizon": selected["horizon"],
        }
    )
    test_pred_path = pred_dir / "test_predictions.csv"
    selected_pred_path = pred_dir / "selected_model_predictions.csv"
    predictions.to_csv(test_pred_path, index=False)
    predictions.to_csv(selected_pred_path, index=False)

    importance = selected_artifacts["model"].feature_importance()
    if importance is not None:
        importance.rename("importance").to_csv(pred_dir.parent / "metrics" / "feature_importance.csv")
        importance_csv = metrics_dir / "feature_importance.csv"
        importance.rename("importance").to_csv(importance_csv, header=True)
    else:
        importance_csv = metrics_dir / "feature_importance.csv"
        pd.DataFrame(columns=["importance"]).to_csv(importance_csv)

    plot_paths = write_evaluation_plots(
        timestamps=predictions["timestamp"],
        y_true=predictions["y_true"].to_numpy(),
        y_pred=predictions["y_pred"].to_numpy(),
        importance=importance,
        output_dir=plots_dir,
    )

    metadata = {
        "modelVersion": config.get("model_version", "1.0.0"),
        "modelType": selected["model"],
        "target": TARGET_COLUMN,
        "unit": config.get("unit", "%"),
        "horizon": selected["horizon"],
        "datasetId": bundle.dataset_id,
        "schemaVersion": bundle.schema_version,
        "features": selected_artifacts["feature_names"],
        "resource": bundle.metadata.get("resource"),
        "origins": bundle.metadata.get("origins"),
        "metrics": {
            "validation": selected_artifacts.get("validation_metrics"),
            "test": {
                "mae": selected.get("mae"),
                "rmse": selected.get("rmse"),
                "smape": selected.get("smape"),
                "latency_mean_ms": selected.get("latency_mean_ms"),
                "latency_p95_ms": selected.get("latency_p95_ms"),
                "high_demand_mae": selected.get("high_demand_mae"),
                "high_demand_rmse": selected.get("high_demand_rmse"),
            },
        },
        "selectionProtocol": {
            "fit": "train",
            "select": "validation",
            "retrain": "train+validation",
            "report": "test",
        },
        "dataKind": "simulated" if "simulated" in (bundle.metadata.get("origins") or []) else "provided",
        "validation": validation_report,
        "horizonSteps": selected_artifacts.get("steps"),
        "frequency": str(selected_artifacts.get("frequency")),
    }
    bundle_path = selected_dir / "model.joblib"
    joblib.dump(
        {
            "model": selected_artifacts["model"],
            "features": selected_artifacts["feature_names"],
            "metadata": metadata,
        },
        bundle_path,
    )
    metadata["modelSha256"] = sha256_file(bundle_path)
    metadata_path = selected_dir / "metadata.json"
    metadata_path.write_text(json.dumps(_jsonable(metadata), indent=2), encoding="utf-8")

    report_path = reports_dir / "model_report.md"
    write_model_report(report_path, bundle.metadata, comparison, selected, notes)

    manifest_path = results_dir / "manifest.json"
    write_manifest(
        manifest_path,
        {
            "datasetId": bundle.dataset_id,
            "datasetSha256": sha256_file(bundle.path),
            "configSha256": sha256_json(config),
            "seed": config.get("random_state"),
            "selected": {
                "model": selected.get("model"),
                "horizon": selected.get("horizon"),
            },
            "validation_metrics": selected_artifacts.get("validation_metrics"),
            "test_metrics": selected_artifacts.get("test_metrics"),
            "modelSha256": metadata["modelSha256"],
            "metadataSha256": sha256_file(metadata_path),
            "dataKind": metadata["dataKind"],
            "note": "Technical run. Not project experimental evidence unless dataKind=observed.",
        },
    )

    return {
        "model": str(bundle_path),
        "metadata": str(metadata_path),
        "comparison": str(comparison_path),
        "validation_comparison": str(validation_comparison_path),
        "selected_metrics": str(selected_metrics_path),
        "validation_metrics": str(validation_metrics_path),
        "test_metrics": str(test_metrics_path),
        "predictions": str(selected_pred_path),
        "test_predictions": str(test_pred_path),
        "feature_importance": str(importance_csv),
        "report": str(report_path),
        "manifest": str(manifest_path),
        **plot_paths,
    }


def _log_mlflow(
    config: dict[str, Any],
    bundle: DatasetBundle,
    selected: dict[str, Any],
    selected_artifacts: dict[str, Any],
    result_paths: dict[str, str],
) -> dict[str, Any]:
    tracker = MLflowTracker(config)
    params = {
        "model_type": selected["model"],
        "target": TARGET_COLUMN,
        "horizon": selected["horizon"],
        "window_size": config.get("features", {}).get("rolling", {}).get("primary_window"),
        "features": selected_artifacts["feature_names"],
        "train_ratio": config["split"]["train_ratio"],
        "validation_ratio": config["split"]["validation_ratio"],
        "test_ratio": config["split"]["test_ratio"],
        "random_state": config.get("random_state", 42),
        "hyperparameters": selected_artifacts["model"].get_params(),
    }
    metrics = {
        "mae": selected.get("mae"),
        "rmse": selected.get("rmse"),
        "smape": selected.get("smape"),
        "latency_mean_ms": selected.get("latency_mean_ms"),
        "latency_p95_ms": selected.get("latency_p95_ms"),
        "high_demand_mae": selected.get("high_demand_mae"),
        "high_demand_rmse": selected.get("high_demand_rmse"),
    }
    tags = {
        "dataset_id": bundle.dataset_id,
        "schema_version": bundle.schema_version,
        "model_version": config.get("model_version", "1.0.0"),
        "git_commit": current_git_commit(),
        "environment": current_environment(config),
    }
    info = {
        "run_id": None,
        "experiment": tracker.experiment_name if tracker.enabled else None,
        "model_version": None,
        "tracking_uri": tracker.tracking_uri if tracker.enabled else None,
    }
    with tracker.start_run(run_name=f"{selected['model']}_{selected['horizon']}") as run:
        artifact_files = [Path(value) for key, value in result_paths.items() if key != "model"]
        run_id = tracker.log_training_run(run, params, metrics, tags, artifact_files)
        registered = tracker.log_model_and_register(selected_artifacts["model"].model if hasattr(selected_artifacts["model"], "model") else selected_artifacts["model"])
        info["run_id"] = run_id or registered.get("run_id")
        info["model_version"] = registered.get("registered_version")
    return info


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return None if value != value else value
    if hasattr(value, "item"):
        try:
            return _jsonable(value.item())
        except Exception:
            return str(value)
    return str(value)
