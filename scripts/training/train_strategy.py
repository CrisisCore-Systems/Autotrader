"""Placeholder training script integrating with MLflow."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import mlflow
from mlflow.pyfunc import PythonModel
import yaml


def load_config(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()

    cfg = load_config(args.config)

    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI")
    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)

    experiment_name = cfg["run"].get("experiment_name", "Autotrader")
    mlflow.set_experiment(experiment_name)

    class PlaceholderModel(PythonModel):
        def predict(self, context, model_input):  # type: ignore[override]
            return model_input

    with mlflow.start_run(tags=cfg["run"].get("tags", {})) as run:
        mlflow.log_params(cfg.get("hyperparameters", {}))
        mlflow.log_metric("sharpe", 1.75)
        mlflow.log_metric("profit_factor", 1.3)

        output_dir = Path(cfg["outputs"]["model_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        model_path = output_dir / "model.json"
        model_path.write_text(json.dumps({"status": "trained"}, indent=2))

        mlflow.log_artifact(str(model_path))

        metrics_path = Path(cfg["outputs"]["metrics_path"])
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        metrics_path.write_text(json.dumps({"sharpe": 1.75, "profit_factor": 1.3}, indent=2))
        mlflow.log_artifact(str(metrics_path))

        mlflow.pyfunc.log_model(
            artifact_path="model",
            registered_model_name=cfg["run"].get("model_name", "autotrader-strategy"),
            python_model=PlaceholderModel(),
            artifacts={"model_config": str(model_path)},
        )

        print(f"Finished training run {run.info.run_id}")


if __name__ == "__main__":
    main()
