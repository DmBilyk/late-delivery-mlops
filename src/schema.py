import pandas as pd


ID_COLUMN = 'order_id'
TIMESTAMP_COLUMN = 'order_purchase_timestamp'
TARGET_COLUMN = 'is_late'

NUMERIC_COLUMNS = [
    'total_price',
    'total_freight',
    'n_items',
    'n_sellers',
    'promised_days',
    'distance_km',
    'product_weight_g',
    'max_installments',
    'total_payment_value',
]

CATEGORICAL_COLUMNS = [
    'product_category_name',
    'payment_type',
    'customer_state',
    'seller_state',
]

# Raw columns a batch must contain (no dummies, no derived features).
INPUT_COLUMNS = {
    **{col: 'numeric' for col in NUMERIC_COLUMNS},
    **{col: 'categorical' for col in CATEGORICAL_COLUMNS},
    'seller_id': 'categorical',
    TIMESTAMP_COLUMN: 'datetime',
}

# Known only after purchase: their presence in a batch means leakage.
FORBIDDEN_COLUMNS = [
    'order_delivered_carrier_date',
    'order_delivered_customer_date',
    'days_diff',
    'order_approved_at',
    'order_status',
    'is_on_time',
    TARGET_COLUMN,
]


class SchemaError(ValueError):
    pass


_TYPE_CHECKS = {
    'numeric': pd.api.types.is_numeric_dtype,
    'categorical': lambda s: pd.api.types.is_string_dtype(s) or pd.api.types.is_object_dtype(s),
    'datetime': pd.api.types.is_datetime64_any_dtype,
}


def validate_schema(df):
    missing = [col for col in INPUT_COLUMNS if col not in df.columns]
    if missing:
        raise SchemaError(f'Missing columns: {missing}')

    forbidden = [col for col in FORBIDDEN_COLUMNS if col in df.columns]
    if forbidden:
        raise SchemaError(f'Forbidden (post-purchase) columns in batch: {forbidden}')

    wrong_types = {
        col: str(df[col].dtype)
        for col, kind in INPUT_COLUMNS.items()
        if not _TYPE_CHECKS[kind](df[col])
    }
    if wrong_types:
        raise SchemaError(f'Wrong column types: {wrong_types}, expected {INPUT_COLUMNS}')

    return df
