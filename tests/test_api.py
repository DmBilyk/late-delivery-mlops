import numpy as np
import pytest
from fastapi.testclient import TestClient

import src.api as api
from src.db import DatabaseUnavailable

ORDER = {
    'order_id': 'o1',
    'order_purchase_timestamp': '2018-05-10T12:00:00',
    'total_price': 100.0,
    'total_freight': 15.0,
    'n_items': 1,
    'n_sellers': 1,
    'promised_days': 20,
    'distance_km': None,
    'product_weight_g': 500.0,
    'max_installments': 1,
    'total_payment_value': 115.0,
    'product_category_name': None,
    'payment_type': 'credit_card',
    'customer_state': 'SP',
    'seller_state': 'RJ',
    'seller_id': 's1',
}


class FakeModel:
    """Returns p_late = 0.7 and keeps the frame it got."""

    def predict_proba(self, X):
        self.X = X
        return np.array([[0.3, 0.7]])


class FakeConnection:
    def close(self):
        pass


@pytest.fixture
def saved(monkeypatch):
    calls = []
    monkeypatch.setattr(api, 'load_champion', lambda: (7, FakeModel()))
    monkeypatch.setattr(api, 'get_connection', lambda: FakeConnection())
    monkeypatch.setattr(api, 'ping', lambda conn: None)
    monkeypatch.setattr(api, 'save_prediction', lambda conn, *args: calls.append(args))
    return calls


@pytest.fixture
def client(saved):
    with TestClient(api.app) as c:
        yield c


def db_down():
    raise DatabaseUnavailable('connection refused')


def test_predict_returns_and_logs_prediction(client, saved):
    r = client.post('/predict', json=ORDER)

    assert r.status_code == 200
    body = r.json()
    assert body['p_late'] == 0.7
    assert body['predicted_late'] is True
    assert body['model_version'] == 7
    assert len(saved) == 1


def test_missing_numeric_value_becomes_float(client):
    client.post('/predict', json=ORDER)
    X = api.state['model'].X
    assert X['distance_km'].dtype == float
    assert X['distance_km'].isna().all()


def test_predict_returns_503_when_database_is_down(client, monkeypatch):
    monkeypatch.setattr(api, 'get_connection', db_down)
    r = client.post('/predict', json=ORDER)
    assert r.status_code == 503
    assert r.json() == {'detail': 'Database unavailable'}


def test_bad_payload_is_rejected(client):
    r = client.post('/predict', json={k: v for k, v in ORDER.items() if k != 'total_price'})
    assert r.status_code == 422


def test_health_ok_and_503(client, monkeypatch):
    assert client.get('/health').status_code == 200
    monkeypatch.setattr(api, 'get_connection', db_down)
    assert client.get('/health').status_code == 503


def test_model_info(client):
    info = client.get('/model-info').json()
    assert info['model_version'] == 7
    assert info['alias'] == 'champion'
