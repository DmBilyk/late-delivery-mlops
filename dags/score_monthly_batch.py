"""Monthly batch scoring: wait for the batch file -> validate schema -> score with the champion
-> load the labels that have arrived -> print monthly metrics.

One DAG run = one batch month (2018-04 .. 2018-08). The month comes from the run's
logical date, or from the `month` param when triggered by hand (backfill of one month).
"""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from airflow.sdk import Param, dag, get_current_context, task

ML_PYTHON = '/opt/ml-venv/bin/python'
PROJECT_DIR = os.environ.get('PROJECT_DIR', '/opt/project')


@task
def resolve_month():
    context = get_current_context()
    month = context['params'].get('month')
    if month:
        return month
    return context['logical_date'].strftime('%Y-%m')


@task.sensor(poke_interval=30, timeout=timedelta(days=7).total_seconds(), mode='reschedule')
def wait_for_batch(month):
    path = Path(PROJECT_DIR) / 'batches' / f'{month}.parquet'
    print(f'waiting for {path}')
    return path.exists()


# The tasks below run in the ML venv: only the function body is shipped there,
# so all imports live inside the function.

@task.external_python(python=ML_PYTHON, expect_airflow=False, retries=0)
def validate(month):
    import os
    import sys
    os.chdir(os.environ['PROJECT_DIR'])
    sys.path.insert(0, os.environ['PROJECT_DIR'])
    from src.batch_scoring import load_config, validate_batch

    return validate_batch(month, load_config())


@task.external_python(python=ML_PYTHON, expect_airflow=False)
def score(month):
    import os
    import sys
    os.chdir(os.environ['PROJECT_DIR'])
    sys.path.insert(0, os.environ['PROJECT_DIR'])
    from src.batch_scoring import load_config, score_batch

    return score_batch(month, load_config())


@task.external_python(python=ML_PYTHON, expect_airflow=False)
def load_actuals():
    import os
    import sys
    os.chdir(os.environ['PROJECT_DIR'])
    sys.path.insert(0, os.environ['PROJECT_DIR'])
    from src.batch_scoring import load_actuals, load_config

    return load_actuals(load_config())


@task.external_python(python=ML_PYTHON, expect_airflow=False)
def report_metrics(month):
    import os
    import sys
    os.chdir(os.environ['PROJECT_DIR'])
    sys.path.insert(0, os.environ['PROJECT_DIR'])
    from src.batch_scoring import report_metrics

    report_metrics(month)


@dag(
    schedule='@monthly',
    start_date=datetime(2018, 4, 1, tzinfo=timezone.utc),
    end_date=datetime(2018, 8, 1, tzinfo=timezone.utc),
    catchup=True,
    max_active_runs=1,
    default_args={'retries': 3, 'retry_delay': timedelta(minutes=1)},
    params={'month': Param(None, type=['null', 'string'], description="Batch month 'YYYY-MM'. Empty = from the logical date.")},
    tags=['ml'],
)
def score_monthly_batch():
    month = resolve_month()
    wait_for_batch(month) >> validate(month) >> score(month) >> load_actuals() >> report_metrics(month)


score_monthly_batch()
