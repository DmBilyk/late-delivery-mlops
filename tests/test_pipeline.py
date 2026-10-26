import pytest

from src.features import build_pipeline
from src.schema import SchemaError


@pytest.fixture
def fitted_pipeline(orders, labels):
    pipeline = build_pipeline({'n_estimators': 10}, min_category_freq=10)
    return pipeline.fit(orders, labels)


def test_predict_proba_shape_and_range(fitted_pipeline, orders):
    proba = fitted_pipeline.predict_proba(orders)[:, 1]
    assert len(proba) == len(orders)
    assert ((proba >= 0) & (proba <= 1)).all()


def test_renamed_column_is_rejected(fitted_pipeline, orders):
    with pytest.raises(SchemaError):
        fitted_pipeline.predict_proba(orders.rename(columns={'distance_km': 'dist'}))
