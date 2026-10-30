FROM python:3.12-slim

RUN pip install --no-cache-dir mlflow==3.17.2 "psycopg[binary]==3.3.6"

# Artifacts volume is created from this folder, so it keeps the owner.
RUN useradd --create-home mlflow && mkdir /mlartifacts && chown mlflow /mlartifacts
USER mlflow
