"""Prepares a fresh Postgres server (RDS): extra databases, then tables and views in `ml`. Safe to run again.

    python -m src.init_db
    docker compose run --rm api python -m src.init_db     # on EC2

Uses DATABASE_URL, which points at the `ml` database (RDS creates it from `db_name`).
"""
from pathlib import Path

from psycopg import sql

from src.db import get_connection

SQL_DIR = Path(__file__).parent.parent / 'sql'
EXTRA_DATABASES = ('mlflow', 'airflow')


def create_databases(conn, names=EXTRA_DATABASES):
    """Postgres has no CREATE DATABASE IF NOT EXISTS, so check pg_database first."""
    for name in names:
        if conn.execute('SELECT 1 FROM pg_database WHERE datname = %s', (name,)).fetchone():
            print(f'database {name}: exists')
        else:
            conn.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
            print(f'database {name}: created')


def apply_schema(conn):
    """schema.sql uses IF NOT EXISTS, views.sql uses CREATE OR REPLACE, so reruns are no-ops."""
    for file in ('schema.sql', 'views.sql'):
        conn.execute((SQL_DIR / file).read_text())
        print(f'{file}: applied')


def main():
    conn = get_connection()
    try:
        create_databases(conn)
        apply_schema(conn)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
