"""Prefect flow orchestrating data fetch, feature build, training, and logging."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import mlflow
import prefect
from prefect import flow, task
from prefect.tasks import task_input_hash

try:
    import wandb
except ImportError:  # pragma: no cover
    wandb = None

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
CONFIG_DIR = REPO_ROOT / "configs"


@task(cache_key_fn=task_input_hash, refresh_cache=True)
def run_dvc_stage(stage: str) -> None:
    subprocess.run(["dvc", "repro", stage], check=True, cwd=REPO_ROOT)


@task
def run_training() -> str:
    train_script = SCRIPTS_DIR / "training" / "train_strategy.py"
    config_path = CONFIG_DIR / "training" / "strategy.yaml"
    result = subprocess.run(
        ["python", str(train_script), "--config", str(config_path)],
        check=True,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    prefect.get_run_logger().info(result.stdout)
    return result.stdout


@task
def log_to_wandb(run_id: str) -> None:
    if wandb is None:
        prefect.get_run_logger().warning("wandb not installed; skipping upload")
        return

    wandb.init(project=os.environ.get("WANDB_PROJECT", "autotrader"), reinit=True)
    wandb.log({"mlflow_run_id": run_id})
    wandb.finish()


@flow(name="autotrader-experiment-pipeline")
def experiment_flow(stage: str = "train_model") -> None:
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000"))

    run_dvc_stage(stage)
    stdout = run_training()

    run = mlflow.last_active_run()
    if run is None:
        raise RuntimeError("No active MLflow run detected")

    prefect.get_run_logger().info("Completed MLflow run %s", run.info.run_id)
    log_to_wandb(run.info.run_id)

    prefect.get_run_logger().info("Training output:\n%s", stdout)


if __name__ == "__main__":  # pragma: no cover
    experiment_flow()
