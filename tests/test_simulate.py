import pandas as pd
import pytest

from src.simulate import next_step, select_month, write_batch, write_labels


@pytest.fixture
def df():
    """Two orders per month: one train month (2017-05) and three batch months."""
    timestamps = ['2017-05-10', '2017-05-20',
                  '2018-04-01', '2018-04-30',
                  '2018-05-10', '2018-05-20',
                  '2018-06-10', '2018-06-20']
    return pd.DataFrame({
        'order_id': [f'o{i}' for i in range(len(timestamps))],
        'distance_km': [100.0] * len(timestamps),
        'order_purchase_timestamp': pd.to_datetime(timestamps),
        'is_late': [0, 1] * 4,
    })


@pytest.fixture
def cfg(tmp_path):
    return {
        'paths': {'batches_dir': tmp_path / 'batches', 'labels_dir': tmp_path / 'labels'},
        'split': {
            'start': '2017-01',
            'train_end': '2017-11',
            'val_end': '2018-01',
            'test_end': '2018-03',
            'batches_end': '2018-06',
        },
    }


def test_select_month_returns_only_that_month(df, cfg):
    rows = select_month(df, '2018-04', cfg['split'])
    assert list(rows['order_id']) == ['o2', 'o3']


def test_select_month_rejects_train_month(df, cfg):
    with pytest.raises(ValueError):
        select_month(df, '2017-05', cfg['split'])


def test_batch_has_no_labels(df, cfg):
    write_batch(df, '2018-04', cfg)
    batch = pd.read_parquet(cfg['paths']['batches_dir'] / '2018-04.parquet')
    assert 'is_late' not in batch.columns
    assert 'order_id' in batch.columns


def test_labels_have_only_id_and_target(df, cfg):
    write_labels(df, '2018-04', cfg)
    labels = pd.read_parquet(cfg['paths']['labels_dir'] / '2018-04.parquet')
    assert list(labels.columns) == ['order_id', 'is_late']


def test_existing_batch_is_not_overwritten(df, cfg):
    assert write_batch(df, '2018-04', cfg) is True
    assert write_batch(df, '2018-04', cfg) is False
    assert write_batch(df, '2018-04', cfg, force=True) is True


def test_rename_makes_broken_batch(df, cfg):
    write_batch(df, '2018-04', cfg, rename={'distance_km': 'dist'})
    batch = pd.read_parquet(cfg['paths']['batches_dir'] / '2018-04.parquet')
    assert 'dist' in batch.columns
    assert 'distance_km' not in batch.columns


def test_next_step_labels_arrive_one_month_later(df, cfg):
    batches = cfg['paths']['batches_dir']
    labels = cfg['paths']['labels_dir']

    next_step(df, cfg)
    assert (batches / '2018-04.parquet').exists()
    assert not labels.exists()

    next_step(df, cfg)
    assert (batches / '2018-05.parquet').exists()
    assert (labels / '2018-04.parquet').exists()
    assert not (labels / '2018-05.parquet').exists()
