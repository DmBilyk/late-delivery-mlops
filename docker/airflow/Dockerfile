FROM apache/airflow:3.3.2-python3.12

# LightGBM needs the OpenMP runtime.
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir /opt/ml-venv && chown airflow /opt/ml-venv
USER airflow

# Our ML code runs in its own venv, so its pinned versions never clash with Airflow's.
COPY requirements.txt /tmp/requirements.txt
RUN python -m venv /opt/ml-venv \
    && /opt/ml-venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt
