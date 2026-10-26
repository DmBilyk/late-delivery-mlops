import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def orders():
    """Small valid batch with all input columns."""
    rng = np.random.default_rng(0)
    n = 200
    return pd.DataFrame({
        'total_price': rng.uniform(10, 500, n),
        'total_freight': rng.uniform(5, 50, n),
        'n_items': rng.integers(1, 4, n),
        'n_sellers': np.ones(n, dtype=int),
        'promised_days': rng.integers(5, 40, n),
        'distance_km': rng.uniform(0, 3000, n),
        'product_weight_g': rng.uniform(100, 5000, n),
        'max_installments': rng.integers(1, 10, n),
        'total_payment_value': rng.uniform(15, 550, n),
        'product_category_name': rng.choice(['beleza_saude', 'esporte_lazer', 'moveis_decoracao'], n),
        'payment_type': rng.choice(['credit_card', 'boleto'], n),
        'customer_state': rng.choice(['SP', 'RJ', 'MG'], n),
        'seller_state': rng.choice(['SP', 'PR'], n),
        'seller_id': rng.choice(['s1', 's2', 's3', 's4'], n),
        'order_purchase_timestamp': pd.date_range('2017-01-01', periods=n, freq='D'),
    })


@pytest.fixture
def labels(orders):
    """Random 0/1 labels, both classes present."""
    rng = np.random.default_rng(1)
    return pd.Series(rng.integers(0, 2, len(orders)))
