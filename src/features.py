import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from src.schema import CATEGORICAL_COLUMNS, INPUT_COLUMNS, TIMESTAMP_COLUMN, validate_schema


DERIVED_CATEGORICAL_COLUMNS = ['route', 'season']


class SchemaValidator(BaseEstimator, TransformerMixin):
    """Fails on a missing/renamed/mistyped column, keeps only INPUT_COLUMNS."""

    def fit(self, X, y=None):
        validate_schema(X)
        return self

    def transform(self, X):
        validate_schema(X)
        return X[list(INPUT_COLUMNS)].copy()


class SellerLateRateEncoder(BaseEstimator, TransformerMixin):
    """Bayesian-smoothed seller late rate.

    On the training data (fit_transform) every order only sees the seller's
    earlier orders (expanding mean in time order), so its own label never leaks.
    On new data (transform) the final train statistics are used.
    """

    def __init__(self, k=5):
        self.k = k

    def fit(self, X, y):
        y = np.asarray(y)
        self.global_late_rate_ = float(y.mean())
        stats = pd.DataFrame({'seller_id': X['seller_id'].to_numpy(), 'late': y}).groupby('seller_id')['late'].agg(['sum', 'count'])
        self.seller_rate_ = (stats['sum'] + self.global_late_rate_ * self.k) / (stats['count'] + self.k)
        return self

    def fit_transform(self, X, y):
        self.fit(X, y)
        frame = pd.DataFrame({
            'seller_id': X['seller_id'].to_numpy(),
            'ts': X[TIMESTAMP_COLUMN].to_numpy(),
            'late': np.asarray(y),
        })
        frame = frame.sort_values('ts', kind='stable')
        grouped = frame.groupby('seller_id')['late']
        prior_late = grouped.cumsum() - frame['late']
        prior_count = grouped.cumcount()
        frame['rate'] = (prior_late + self.global_late_rate_ * self.k) / (prior_count + self.k)

        X = X.copy()
        X['seller_late_rate'] = frame['rate'].sort_index().to_numpy()
        return X

    def transform(self, X):
        X = X.copy()
        X['seller_late_rate'] = X['seller_id'].map(self.seller_rate_).astype(float).fillna(self.global_late_rate_)
        return X


class FeatureEngineer(BaseEstimator, TransformerMixin):
    """Stateless derived features; drops seller_id and the purchase timestamp."""

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        X = X.copy()
        for col in CATEGORICAL_COLUMNS:
            X[col] = X[col].fillna('Unknown').astype(str)

        X['price_per_item'] = X['total_price'] / X['n_items']
        X['is_interstate'] = (X['customer_state'] != X['seller_state']).astype(int)
        X['days_per_100km'] = X['promised_days'] / ((X['distance_km'] / 100) + 1)
        X['promised_days_vs_distance'] = X['promised_days'] / (X['distance_km'] + 1)
        X['freight_per_gram'] = X['total_freight'] / (X['product_weight_g'] + 1)
        X['route'] = X['seller_state'] + '_' + X['customer_state']

        ts = X[TIMESTAMP_COLUMN]
        X['purchase_dayofweek'] = ts.dt.dayofweek
        X['purchase_month'] = ts.dt.month
        X['purchase_hour'] = ts.dt.hour
        X['season'] = (ts.dt.month % 12 // 3).map({0: 'winter', 1: 'spring', 2: 'summer', 3: 'autumn'})

        return X.drop(columns=['seller_id', TIMESTAMP_COLUMN])


def build_pipeline(model_params, seller_k=5, min_category_freq=500, seed=42):
    encoder = ColumnTransformer(
        [(
            'onehot',
            OneHotEncoder(handle_unknown='infrequent_if_exist', min_frequency=min_category_freq, sparse_output=False),
            CATEGORICAL_COLUMNS + DERIVED_CATEGORICAL_COLUMNS,
        )],
        remainder='passthrough',
        verbose_feature_names_out=False,
    ).set_output(transform='pandas')

    model = lgb.LGBMClassifier(objective='binary', random_state=seed, n_jobs=1, verbose=-1, **model_params)

    return Pipeline([
        ('validate', SchemaValidator()),
        ('seller_rate', SellerLateRateEncoder(k=seller_k)),
        ('features', FeatureEngineer()),
        ('encode', encoder),
        ('model', model),
    ])
