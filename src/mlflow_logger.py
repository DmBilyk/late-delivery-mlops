import json
import yaml
import mlflow
import joblib

from src.mlflow_config import MODEL_NAME, TRACKING_URI


def flatten(d, prefix=""):
    flat = {}
    for key, value in d.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(flatten(value, f"{name}."))
        else:
            flat[name] = value
    return flat


def log_experiment(params_path: str, metrics_path: str, model_path: str):
    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment("late-delivery")

    with open(params_path) as f:
        params = yaml.safe_load(f)

    with open(metrics_path) as f:
        metrics = json.load(f)

    model = joblib.load(model_path)

    with mlflow.start_run():

        config = flatten(params)
        config = {k: v for k, v in config.items() if not k.startswith("paths.")}
        mlflow.log_params(config)

        for split, values in metrics.items():
            mlflow.log_metrics({
                f"{split}_{key}": value
                for key, value in values.items()
                if key != "threshold"
            })

        mlflow.sklearn.log_model(
            model,
            name="model",
            registered_model_name=MODEL_NAME,
            serialization_format="cloudpickle",
        )

        mlflow.log_artifact(params_path)
        mlflow.log_artifact(metrics_path)
