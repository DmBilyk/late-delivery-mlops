FROM python:3.12-slim

# boto3: artifacts go to S3 on EC2 (credentials come from the instance IAM role)
RUN pip install --no-cache-dir mlflow==3.17.2 "psycopg[binary]==3.3.6" boto3==1.43.123

# Artifacts volume is created from this folder, so it keeps the owner.
RUN useradd --create-home mlflow && mkdir /mlartifacts && chown mlflow /mlartifacts
USER mlflow
