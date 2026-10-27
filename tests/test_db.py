import os
from pathlib import Path

import pandas as pd
import pytest

from src.db import (
    DEFAULT_URL, DatabaseUnavailable, finish_batch_run, get_connection,
    save_actuals, save_prediction, save_predictions, start_batch_run,
)

SQL_DIR = Path(__file__).parent.parent / 'sql'
THRESHOLD = 0.405


@pytest.fixture(scope='module')
def test_db():
    """Empty `ml_test` database with the real schema and views. Skipped if Postgres is down."""
    try:
        admin = get_connection()
    except DatabaseUnavailable:
        pytest.skip('Postgres is not running')

    admin.execute('DROP DATABASE IF EXISTS ml_test')
    admin.execute('CREATE DATABASE ml_test')
    base_url = os.environ.get('DATABASE_URL', DEFAULT_URL)
    conn = get_connection(base_url.rsplit('/', 1)[0] + '/ml_test')
    conn.execute((SQL_DIR / 'schema.sql').read_text())
    conn.execute((SQL_DIR / 'views.sql').read_text())

    yield conn

    conn.close()
    admin.execute('DROP DATABASE ml_test')
    admin.close()


@pytest.fixture
def conn(test_db):
    test_db.execute('TRUNCATE actuals, predictions, batch_runs RESTART IDENTITY CASCADE')
    return test_db


@pytest.fixture
def scored():
    return pd.DataFrame({
        'order_id': ['o1', 'o2', 'o3', 'o4'],
        'order_purchase_timestamp': pd.to_datetime(['2018-04-01'] * 4),
        'p_late': [0.9, 0.2, 0.6, 0.1],
    })


def test_failed_run_shows_in_failures_view(conn):
    run_id = start_batch_run(conn, '2018-05', 'late_delivery', 1)
    finish_batch_run(conn, run_id, 'failed', error='Missing columns')

    rows = conn.execute('SELECT run_id, error FROM v_batch_failures').fetchall()
    assert rows == [(run_id, 'Missing columns')]


def test_save_predictions_is_idempotent(conn, scored):
    run_id = start_batch_run(conn, '2018-04', 'late_delivery', 1)

    assert save_predictions(conn, run_id, scored, 1, THRESHOLD) == 4
    assert save_predictions(conn, run_id, scored, 1, THRESHOLD) == 0
    assert conn.execute('SELECT count(*) FROM predictions').fetchone()[0] == 4


def test_predicted_late_follows_threshold(conn, scored):
    run_id = start_batch_run(conn, '2018-04', 'late_delivery', 1)
    save_predictions(conn, run_id, scored, 1, THRESHOLD)

    rows = conn.execute('SELECT order_id, predicted_late FROM predictions ORDER BY order_id').fetchall()
    assert rows == [('o1', True), ('o2', False), ('o3', True), ('o4', False)]


def test_monthly_metrics_after_actuals_arrive(conn, scored):
    run_id = start_batch_run(conn, '2018-04', 'late_delivery', 1)
    save_predictions(conn, run_id, scored, 1, THRESHOLD)
    finish_batch_run(conn, run_id, 'success', n_rows=4)

    query = 'SELECT n_with_actuals, recall_late, precision_late FROM v_monthly_metrics'
    assert conn.execute(query).fetchone() == (0, None, None)

    labels = pd.DataFrame({'order_id': ['o1', 'o2', 'o3', 'o4'], 'is_late': [1, 1, 0, 0]})
    assert save_actuals(conn, '2018-04', labels) == 4
    assert save_actuals(conn, '2018-04', labels) == 0

    n_with_actuals, recall, precision = conn.execute(query).fetchone()
    assert n_with_actuals == 4
    assert float(recall) == 0.5
    assert float(precision) == 0.5


def test_api_prediction_has_no_batch_run(conn):
    save_prediction(conn, 'o9', pd.Timestamp('2018-04-17 10:00'), 1, 0.7, THRESHOLD)

    row = conn.execute('SELECT source, batch_run_id, purchase_month, predicted_late FROM predictions').fetchone()
    assert row[0] == 'api'
    assert row[1] is None
    assert str(row[2]) == '2018-04-01'
    assert row[3] is True


def test_unreachable_database_raises_clean_error():
    with pytest.raises(DatabaseUnavailable):
        get_connection('postgresql://ml:ml@127.0.0.1:1/ml')
