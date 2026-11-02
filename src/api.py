"""Online scoring API.

    uvicorn src.api:app --host 0.0.0.0 --port 8000

The champion is loaded once at startup; restart the service after `registry promote/rollback`.
"""
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import mlflow
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.batch_scoring import champion_version, load_config
from src.db import DatabaseUnavailable, get_connection, ping, save_prediction
from src.mlflow_config import MODEL_NAME, TRACKING_URI
from src.schema import NUMERIC_COLUMNS


class Order(BaseModel):
    order_id: str
    order_purchase_timestamp: datetime
    total_price: float
    total_freight: float
    n_items: int
    n_sellers: int
    promised_days: int
    distance_km: float | None = None
    product_weight_g: float | None = None
    max_installments: float | None = None
    total_payment_value: float | None = None
    product_category_name: str | None = None
    payment_type: str | None = None
    customer_state: str
    seller_state: str
    seller_id: str


class Prediction(BaseModel):
    order_id: str
    p_late: float
    predicted_late: bool
    model_version: int
    threshold: float


state = {}


def load_champion():
    version = champion_version()
    mlflow.set_tracking_uri(TRACKING_URI)
    return version, mlflow.sklearn.load_model(f'models:/{MODEL_NAME}/{version}')


@asynccontextmanager
async def lifespan(app):
    # Fails fast if MLflow is down; the container restart policy retries.
    state['threshold'] = load_config()['threshold']
    state['version'], state['model'] = load_champion()
    state['loaded_at'] = datetime.now(timezone.utc).isoformat()
    yield


app = FastAPI(title='Late delivery API', lifespan=lifespan)


def to_frame(order):
    row = order.model_dump()
    ts = row['order_purchase_timestamp']
    if ts.tzinfo is not None:
        row['order_purchase_timestamp'] = ts.astimezone(timezone.utc).replace(tzinfo=None)
    X = pd.DataFrame([row])
    X[NUMERIC_COLUMNS] = X[NUMERIC_COLUMNS].astype(float)
    return X


@app.post('/predict', response_model=Prediction)
def predict(order: Order):
    X = to_frame(order)
    p_late = float(state['model'].predict_proba(X)[:, 1][0])

    try:
        conn = get_connection()
        try:
            save_prediction(conn, order.order_id, X['order_purchase_timestamp'].iloc[0],
                            state['version'], p_late, state['threshold'])
        finally:
            conn.close()
    except DatabaseUnavailable:
        raise HTTPException(status_code=503, detail='Database unavailable')

    return Prediction(
        order_id=order.order_id,
        p_late=p_late,
        predicted_late=p_late >= state['threshold'],
        model_version=state['version'],
        threshold=state['threshold'],
    )


@app.get('/health')
def health():
    try:
        conn = get_connection()
        try:
            ping(conn)
        finally:
            conn.close()
    except DatabaseUnavailable:
        return JSONResponse(status_code=503, content={'status': 'unavailable', 'database': 'down'})
    return {'status': 'ok', 'database': 'up', 'model_version': state['version']}


@app.get('/model-info')
def model_info():
    return {
        'model_name': MODEL_NAME,
        'alias': 'champion',
        'model_version': state['version'],
        'threshold': state['threshold'],
        'loaded_at': state['loaded_at'],
    }
