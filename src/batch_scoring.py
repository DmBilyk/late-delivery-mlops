"""Steps of the monthly batch DAG. Plain functions, no Airflow imports, so they run in the ML venv."""
from pathlib import Path

import mlflow
import pandas as pd
import yaml

from src.db import (
    fetch_monthly_metrics, finish_batch_run, get_connection, save_actuals, save_predictions, start_batch_run,
)
from src.mlflow_config import MODEL_NAME, TRACKING_URI
from src.schema import ID_COLUMN, TIMESTAMP_COLUMN, SchemaError, validate_schema


def load_config(path='config.yaml'):
    with open(path) as f:
        return yaml.safe_load(f)


def batch_path(cfg, month):
    return Path(cfg['paths']['batches_dir']) / f'{month}.parquet'


def champion_version():
    client = mlflow.MlflowClient(TRACKING_URI)
    return int(client.get_model_version_by_alias(MODEL_NAME, 'champion').version)


def validate_batch(month, cfg):
    """Fails on a bad schema and records a failed run. Writes no predictions."""
    df = pd.read_parquet(batch_path(cfg, month))
    try:
        if ID_COLUMN not in df.columns:
            raise SchemaError(f'Missing columns: [{ID_COLUMN!r}]')
        validate_schema(df)
    except SchemaError as e:
        conn = get_connection()
        run_id = start_batch_run(conn, month, MODEL_NAME, champion_version())
        finish_batch_run(conn, run_id, 'failed', error=str(e))
        raise
    print(f'{month}: {len(df)} rows, schema ok')
    return len(df)


def write_predictions_file(scored, month, cfg):
    """predictions/<month>.parquet, replaced by every new run (history stays in Postgres)."""
    path = Path(cfg['paths']['predictions_dir']) / f'{month}.parquet'
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.parquet.tmp')
    scored.to_parquet(tmp, index=False)
    tmp.replace(path)
    return path


def score_batch(month, cfg):
    """Scores the batch with the current champion and writes predictions to a file and Postgres."""
    version = champion_version()
    mlflow.set_tracking_uri(TRACKING_URI)
    # Load by number, not alias: the alias may move while we are running.
    model = mlflow.sklearn.load_model(f'models:/{MODEL_NAME}/{version}')
    threshold = cfg['threshold']

    conn = get_connection()
    run_id = start_batch_run(conn, month, MODEL_NAME, version)
    try:
        df = pd.read_parquet(batch_path(cfg, month))
        scored = df[[ID_COLUMN, TIMESTAMP_COLUMN]].assign(p_late=model.predict_proba(df)[:, 1])

        path = write_predictions_file(
            scored.assign(predicted_late=scored['p_late'] >= threshold,
                          run_id=run_id, model_version=version, threshold=threshold),
            month, cfg,
        )
        n_rows = save_predictions(conn, run_id, scored, version, threshold)
        finish_batch_run(conn, run_id, 'success', n_rows=n_rows)
    except Exception as e:
        finish_batch_run(conn, run_id, 'failed', error=str(e))
        raise

    print(f'{month}: run {run_id}, model v{version}, {n_rows} predictions -> {path} + postgres')
    return {'run_id': run_id, 'model_version': version, 'n_rows': n_rows}


def load_actuals(cfg):
    """Loads every labels file that has arrived. Already loaded orders are skipped, so reruns are safe."""
    conn = get_connection()
    total = 0
    for path in sorted(Path(cfg['paths']['labels_dir']).glob('*.parquet')):
        n_new = save_actuals(conn, path.stem, pd.read_parquet(path))
        print(f'{path.stem}: {n_new} new actuals')
        total += n_new
    return total


def report_metrics(month):
    """Prints v_monthly_metrics up to this month; labelled months show recall and precision."""
    rows = [r for r in fetch_monthly_metrics(get_connection()) if r['month'] <= month]
    for r in rows:
        if r['recall_late'] is None:
            print(f"{r['month']}  model v{r['model_version']}  {r['n_predictions']} predictions, labels not arrived yet")
        else:
            print(f"{r['month']}  model v{r['model_version']}  recall={r['recall_late']:.3f}  "
                  f"precision={r['precision_late']:.3f}  ({r['n_with_actuals']} labelled)")
