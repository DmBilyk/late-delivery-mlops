import pandas as pd


def assign_split(timestamps, split_cfg):
    """Maps each purchase timestamp to train / val / test / batch by month (bounds inclusive).

    Months outside [start, batches_end] get None and are not used.
    """
    month = pd.to_datetime(timestamps).dt.to_period('M')
    bounds = {key: pd.Period(value, 'M') for key, value in split_cfg.items()}

    split = pd.Series(None, index=month.index, dtype=object)
    split[(month >= bounds['start']) & (month <= bounds['train_end'])] = 'train'
    split[(month > bounds['train_end']) & (month <= bounds['val_end'])] = 'val'
    split[(month > bounds['val_end']) & (month <= bounds['test_end'])] = 'test'
    split[(month > bounds['test_end']) & (month <= bounds['batches_end'])] = 'batch'
    return split
