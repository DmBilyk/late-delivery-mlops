"""Postgres access for batch_runs, predictions and actuals (database `ml`).

Every function takes an open connection and commits its own work, so a failed
run keeps its batch_runs row and the error stays visible in v_batch_failures.
"""
import functools
import os
from datetime import date

import psycopg

DEFAULT_URL = 'postgresql://ml:ml@localhost:5432/ml'


class DatabaseUnavailable(Exception):
    """The database cannot be reached (the API turns this into a 503)."""


def get_connection(url=None):
    url = url or os.environ.get('DATABASE_URL', DEFAULT_URL)
    try:
        return psycopg.connect(url, autocommit=True, connect_timeout=3)
    except psycopg.OperationalError as e:
        raise DatabaseUnavailable(str(e)) from e


def _db_errors(func):
    """Connection problems during a query also become DatabaseUnavailable."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except psycopg.OperationalError as e:
            raise DatabaseUnavailable(str(e)) from e
    return wrapper


def month_start(month):
    """'2018-04' -> date(2018, 4, 1)"""
    return date.fromisoformat(f'{month}-01')


@_db_errors
def ping(conn):
    conn.execute('SELECT 1')


@_db_errors
def start_batch_run(conn, month, model_name, model_version):
    row = conn.execute(
        'INSERT INTO batch_runs (month, model_name, model_version) '
        'VALUES (%s, %s, %s) RETURNING run_id',
        (month_start(month), model_name, model_version),
    ).fetchone()
    return row[0]


@_db_errors
def finish_batch_run(conn, run_id, status, n_rows=None, error=None):
    conn.execute(
        'UPDATE batch_runs SET status = %s, n_rows = %s, error = %s, finished_at = now() '
        'WHERE run_id = %s',
        (status, n_rows, error, run_id),
    )


@_db_errors
def save_predictions(conn, run_id, df, model_version, threshold):
    """df has order_id, order_purchase_timestamp and p_late. Returns rows inserted."""
    months = df['order_purchase_timestamp'].dt.to_period('M').dt.to_timestamp().dt.date
    rows = [
        (order_id, run_id, month, model_version, p_late, bool(p_late >= threshold), threshold)
        for order_id, month, p_late in zip(df['order_id'].tolist(), months.tolist(), df['p_late'].tolist())
    ]
    with conn.transaction():
        cur = conn.cursor()
        cur.executemany(
            "INSERT INTO predictions (order_id, source, batch_run_id, purchase_month, "
            "model_version, p_late, predicted_late, threshold) "
            "VALUES (%s, 'batch', %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (batch_run_id, order_id) DO NOTHING",
            rows,
        )
        return cur.rowcount


@_db_errors
def save_prediction(conn, order_id, purchase_timestamp, model_version, p_late, threshold):
    """One prediction from the API (no batch run)."""
    conn.execute(
        "INSERT INTO predictions (order_id, source, purchase_month, "
        "model_version, p_late, predicted_late, threshold) "
        "VALUES (%s, 'api', %s, %s, %s, %s, %s)",
        (order_id, purchase_timestamp.replace(day=1).date(), model_version,
         p_late, bool(p_late >= threshold), threshold),
    )


@_db_errors
def save_actuals(conn, month, df):
    """df has order_id and is_late; month is the purchase month of the labels file."""
    rows = [
        (order_id, month_start(month), bool(is_late))
        for order_id, is_late in zip(df['order_id'].tolist(), df['is_late'].tolist())
    ]
    with conn.transaction():
        cur = conn.cursor()
        cur.executemany(
            'INSERT INTO actuals (order_id, purchase_month, is_late) VALUES (%s, %s, %s) '
            'ON CONFLICT (order_id) DO NOTHING',
            rows,
        )
        return cur.rowcount
