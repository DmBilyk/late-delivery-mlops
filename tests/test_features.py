import pandas as pd
import pytest

from src.features import FeatureEngineer, SchemaValidator, SellerLateRateEncoder
from src.schema import INPUT_COLUMNS


def test_schema_validator_keeps_only_input_columns(orders):
    out = SchemaValidator().fit_transform(orders.assign(order_id='x'))
    assert list(out.columns) == list(INPUT_COLUMNS)


def test_feature_engineer_derived_columns(orders):
    X = orders.head(2).copy()
    X['total_price'] = [100.0, 30.0]
    X['n_items'] = [2, 3]
    X['customer_state'] = ['SP', 'RJ']
    X['seller_state'] = ['SP', 'PR']
    X['order_purchase_timestamp'] = pd.to_datetime(['2017-12-15', '2017-07-01'])

    out = FeatureEngineer().fit_transform(X)

    assert list(out['price_per_item']) == [50.0, 10.0]
    assert list(out['is_interstate']) == [0, 1]
    assert list(out['route']) == ['SP_SP', 'PR_RJ']
    assert list(out['season']) == ['winter', 'summer']


def test_feature_engineer_fills_missing_category(orders):
    X = orders.head(1).copy()
    X['product_category_name'] = [None]
    out = FeatureEngineer().fit_transform(X)
    assert out['product_category_name'].iloc[0] == 'Unknown'


def test_feature_engineer_drops_id_and_timestamp(orders):
    out = FeatureEngineer().fit_transform(orders)
    assert 'seller_id' not in out.columns
    assert 'order_purchase_timestamp' not in out.columns


def test_seller_rate_uses_only_earlier_orders():
    # Rows are not in time order on purpose
    X = pd.DataFrame({
        'seller_id': ['a', 'a', 'b'],
        'order_purchase_timestamp': pd.to_datetime(['2017-01-02', '2017-01-01', '2017-01-03']),
    })
    y = [0, 1, 0]
    k = 5
    prior = 1 / 3

    out = SellerLateRateEncoder(k=k).fit_transform(X, y)
    rate = out['seller_late_rate']

    # First order of a seller sees only the prior, not its own label
    assert rate[1] == pytest.approx(prior)
    assert rate[2] == pytest.approx(prior)
    # Second order of 'a' sees the first one (late)
    assert rate[0] == pytest.approx((1 + prior * k) / (1 + k))


def test_seller_rate_unseen_seller_gets_global_rate():
    X = pd.DataFrame({
        'seller_id': ['a', 'b'],
        'order_purchase_timestamp': pd.to_datetime(['2017-01-01', '2017-01-02']),
    })
    encoder = SellerLateRateEncoder().fit(X, [1, 0])

    out = encoder.transform(pd.DataFrame({'seller_id': ['new']}))

    assert out['seller_late_rate'].iloc[0] == pytest.approx(0.5)
