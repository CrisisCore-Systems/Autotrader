"""Utility for registering and promoting models in MLflow."""

from __future__ import annotations

import argparse
import os

import mlflow


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Register models in MLflow and transition stages.")
    parser.add_argument("--run-id", required=True, help="MLflow run ID containing the logged model")
    parser.add_argument(
        "--model-name",
        default=os.environ.get("MODEL_NAME", "autotrader-strategy"),
        help="Registered model name",
    )
    parser.add_argument(
        "--stage",
        choices=["None", "Staging", "Production"],
        default="None",
        help="Target stage for the model",
    )
    parser.add_argument(
        "--comment",
        default="",
        help="Optional description for the registration event",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI")
    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)

    client = mlflow.tracking.MlflowClient()

    model_uri = f"runs:/{args.run_id}/model"
    result = mlflow.register_model(model_uri=model_uri, name=args.model_name)

    if args.stage != "None":
        client.transition_model_version_stage(
            name=result.name,
            version=result.version,
            stage=args.stage,
            archive_existing_versions=args.stage == "Production",
        )

    if args.comment:
        client.set_model_version_tag(result.name, result.version, "comment", args.comment)

    print(
        f"Registered {result.name} v{result.version} from run {args.run_id}"
        f" (stage={args.stage})"
    )


if __name__ == "__main__":
    main()
