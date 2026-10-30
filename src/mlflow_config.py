import os

# Local default is the compose MLflow server; containers set MLFLOW_TRACKING_URI=http://mlflow:5000.
TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://127.0.0.1:5001")
MODEL_NAME = "late_delivery"
