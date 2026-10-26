import pandas as pd

from src.split import assign_split

SPLIT = {
    'start': '2017-01',
    'train_end': '2017-11',
    'val_end': '2018-01',
    'test_end': '2018-03',
    'batches_end': '2018-08',
}

def test_month_boundaries():
    timestamps = pd.Series(pd.to_datetime([
        '2017-11-30 23:59',   # last day train
        '2017-12-01 00:00',   # first day val
        '2018-02-01 00:00',   # first day test
        '2018-04-01 00:00',   # first day batch
    ]))


    result = assign_split(timestamps, SPLIT)

    assert list(result) == ['train','val','test','batch']


def test_out_of_range_is_none():
    timestamps = pd.Series(pd.to_datetime([
        '2016-12-31 23:59',  # day before start
        '2018-09-01 00:00',  # day after batches_end
    ]))

    result = assign_split(timestamps, SPLIT)

    assert result.isna().all()