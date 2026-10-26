"""Simulates monthly data arrival: features first, labels one month later.

    python -m src.simulate batch 2018-04
    python -m src.simulate batch 2018-05 --rename distance_km=dist
    python -m src.simulate labels 2018-04
    python -m src.simulate next
"""
import argparse
from pathlib import Path

import pandas as pd
import yaml

from src.schema import ID_COLUMN, TARGET_COLUMN, TIMESTAMP_COLUMN
from src.split import assign_split

# Labels for month M arrive together with the batch of month M + LABEL_DELAY.
LABEL_DELAY = 1


def load_data(cfg):
    features = pd.read_parquet(cfg['paths']['features'])
    labels = pd.read_parquet(cfg['paths']['labels'])
    df = features.merge(labels, on=ID_COLUMN, how='inner', validate='one_to_one')
    return df


def select_month(df, month, split_cfg):
    months = df[TIMESTAMP_COLUMN].dt.to_period('M')
    rows = df[months == pd.Period(month, 'M')]
    if rows.empty or (assign_split(rows[TIMESTAMP_COLUMN], split_cfg) != 'batch').any():
        raise ValueError(f'{month} is not a batch month')
    return rows


def batch_months(split_cfg):
    """All batch months in order: ['2018-04', ..., '2018-08']."""
    first = pd.Period(split_cfg['test_end'], 'M') + 1
    last = pd.Period(split_cfg['batches_end'], 'M')
    return [str(month) for month in pd.period_range(first, last, freq='M')]


def _write_atomic(rows, path, force):
    if path.exists() and not force:
        print(f'{path} already exists, skipping (use --force to overwrite)')
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.parquet.tmp')
    rows.to_parquet(tmp, index=False)
    tmp.replace(path)
    print(f'wrote {path} ({len(rows)} rows)')
    return True


def write_batch(df, month, cfg, force=False, rename=None):
    rows = select_month(df, month, cfg['split']).drop(columns=[TARGET_COLUMN])
    if rename:
        rows = rows.rename(columns=rename)
    path = Path(cfg['paths']['batches_dir']) / f'{month}.parquet'
    return _write_atomic(rows, path, force)


def write_labels(df, month, cfg, force=False):
    rows = select_month(df, month, cfg['split'])[[ID_COLUMN, TARGET_COLUMN]]
    path = Path(cfg['paths']['labels_dir']) / f'{month}.parquet'
    return _write_atomic(rows, path, force)


def next_step(df, cfg):
    """One tick of time: the next missing batch plus the labels that are due by then."""
    months = batch_months(cfg['split'])
    batches_dir = Path(cfg['paths']['batches_dir'])
    labels_dir = Path(cfg['paths']['labels_dir'])

    pending = [m for m in months if not (batches_dir / f'{m}.parquet').exists()]
    if pending:
        month = pending[0]
        write_batch(df, month, cfg)
        due = months[:months.index(month) + 1 - LABEL_DELAY]
    else:
        # All batches are out: the remaining labels arrive one per tick.
        due = months

    missing = [m for m in due if not (labels_dir / f'{m}.parquet').exists()]
    if missing:
        write_labels(df, missing[0], cfg)
    elif not pending:
        print('simulation finished: all batches and labels are out')


def parse_rename(value):
    """'old=new' -> {'old': 'new'}"""
    old, new = value.split('=')
    return {old: new}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='config.yaml')
    commands = parser.add_subparsers(dest='command', required=True)

    batch = commands.add_parser('batch')
    batch.add_argument('month')
    batch.add_argument('--force', action='store_true')
    batch.add_argument('--rename', type=parse_rename, help='old=new, makes a broken batch')

    labels = commands.add_parser('labels')
    labels.add_argument('month')
    labels.add_argument('--force', action='store_true')

    commands.add_parser('next')

    args = parser.parse_args()
    with open(args.config) as f:
        cfg = yaml.safe_load(f)
    df = load_data(cfg)

    if args.command == 'batch':
        write_batch(df, args.month, cfg, force=args.force, rename=args.rename)
    elif args.command == 'labels':
        write_labels(df, args.month, cfg, force=args.force)
    else:
        next_step(df, cfg)


if __name__ == '__main__':
    main()
