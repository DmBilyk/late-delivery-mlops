"""Joins the raw Olist tables into one order-level table.

Writes:
    data/features.parquet  order_id + INPUT_COLUMNS (no labels, no post-purchase columns)
    data/labels.parquet    order_id, is_late
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from src.schema import ID_COLUMN, INPUT_COLUMNS, TARGET_COLUMN, TIMESTAMP_COLUMN


def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return R * 2 * np.arcsin(np.sqrt(a))


def load_raw(raw_dir):
    raw_dir = Path(raw_dir)
    return {
        'customers': pd.read_csv(raw_dir / 'olist_customers_dataset.csv'),
        'geo': pd.read_csv(raw_dir / 'olist_geolocation_dataset.csv'),
        'order_items': pd.read_csv(raw_dir / 'olist_order_items_dataset.csv'),
        'payments': pd.read_csv(raw_dir / 'olist_order_payments_dataset.csv'),
        'orders': pd.read_csv(raw_dir / 'olist_orders_dataset.csv'),
        'products': pd.read_csv(raw_dir / 'olist_products_dataset.csv'),
        'sellers': pd.read_csv(raw_dir / 'olist_sellers_dataset.csv'),
    }


def build_order_table(raw):
    orders = raw['orders'].dropna(subset=['order_delivered_customer_date']).copy()
    for col in [TIMESTAMP_COLUMN, 'order_delivered_customer_date', 'order_estimated_delivery_date']:
        orders[col] = pd.to_datetime(orders[col])

    orders[TARGET_COLUMN] = (
        (orders['order_delivered_customer_date'] - orders['order_estimated_delivery_date']).dt.days > 0
    ).astype(int)
    orders['promised_days'] = (orders['order_estimated_delivery_date'] - orders[TIMESTAMP_COLUMN]).dt.days

    items = raw['order_items']
    order_features = items.groupby('order_id').agg(
        total_price=('price', 'sum'),
        total_freight=('freight_value', 'sum'),
        n_items=('order_item_id', 'count'),
        n_sellers=('seller_id', 'nunique'),
        seller_id=('seller_id', 'first'),
        product_id=('product_id', 'first'),
    ).reset_index()

    df = orders.merge(order_features, on='order_id', how='left')
    df = df.merge(raw['customers'][['customer_id', 'customer_zip_code_prefix', 'customer_state']], on='customer_id', how='left')
    df = df.merge(raw['sellers'][['seller_id', 'seller_zip_code_prefix', 'seller_state']], on='seller_id', how='left')

    geo_agg = raw['geo'].groupby('geolocation_zip_code_prefix').agg(
        lat=('geolocation_lat', 'mean'),
        lng=('geolocation_lng', 'mean'),
    )
    customer_geo = geo_agg.reindex(df['customer_zip_code_prefix'])
    seller_geo = geo_agg.reindex(df['seller_zip_code_prefix'])
    df['distance_km'] = haversine(customer_geo['lat'].to_numpy(), customer_geo['lng'].to_numpy(),
                                  seller_geo['lat'].to_numpy(), seller_geo['lng'].to_numpy())

    df = df.merge(raw['products'][['product_id', 'product_category_name', 'product_weight_g']], on='product_id', how='left')

    payment_features = raw['payments'].groupby('order_id').agg(
        total_payment_value=('payment_value', 'sum'),
        max_installments=('payment_installments', 'max'),
        payment_type=('payment_type', 'first'),
    ).reset_index()
    df = df.merge(payment_features, on='order_id', how='left')

    df = df.sort_values(TIMESTAMP_COLUMN).reset_index(drop=True)

    features = df[[ID_COLUMN] + list(INPUT_COLUMNS)]
    labels = df[[ID_COLUMN, TARGET_COLUMN]]
    return features, labels


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--raw-dir', default='.')
    parser.add_argument('--out-dir', default='data')
    args = parser.parse_args()

    features, labels = build_order_table(load_raw(args.raw_dir))

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    features.to_parquet(out_dir / 'features.parquet', index=False)
    labels.to_parquet(out_dir / 'labels.parquet', index=False)
    print(f'{len(features)} orders, late rate {labels[TARGET_COLUMN].mean():.3f} -> {out_dir}')


if __name__ == '__main__':
    main()
