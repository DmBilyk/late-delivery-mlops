import pytest

from src.schema import SchemaError, validate_schema


def test_valid_batch_passes(orders):
    assert validate_schema(orders) is orders


def test_renamed_column_fails(orders):
    batch = orders.rename(columns={'distance_km': 'dist'})
    with pytest.raises(SchemaError, match='distance_km'):
        validate_schema(batch)


def test_forbidden_column_fails(orders):
    # Delivery date is known only after purchase -> leakage
    batch = orders.assign(order_delivered_customer_date=orders['order_purchase_timestamp'])
    with pytest.raises(SchemaError, match='Forbidden'):
        validate_schema(batch)


def test_wrong_type_fails(orders):
    batch = orders.assign(total_price=orders['total_price'].astype(str))
    with pytest.raises(SchemaError, match='total_price'):
        validate_schema(batch)
