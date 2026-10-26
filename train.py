"""Trains the late-delivery pipeline on the train months and evaluates it on val / test.

Reads:
    config.yaml            split months, model params, threshold, paths
    data/features.parquet  order_id + INPUT_COLUMNS
    data/labels.parquet    order_id, is_late

Writes:
    models/pipeline.joblib  fitted sklearn Pipeline (validation + features + model)
    models/metrics.json     val / test metrics at the config threshold
"""
import argparse
import json
import time
from pathlib import Path

import joblib
import pandas as pd
import yaml

from src.features import build_pipeline
from src.metrics import evaluate
from src.schema import ID_COLUMN, INPUT_COLUMNS, TARGET_COLUMN, TIMESTAMP_COLUMN
from src.split import assign_split
from src.mlflow_logger import log_experiment





def load_config(path):
    with open(path) as f:
        return yaml.safe_load(f)


def load_dataset(cfg):
    features = pd.read_parquet(cfg['paths']['features'])
    labels = pd.read_parquet(cfg['paths']['labels'])
    df = features.merge(labels, on=ID_COLUMN, how='inner', validate='one_to_one')
    df['split'] = assign_split(df[TIMESTAMP_COLUMN], cfg['split'])
    return df


def train(cfg):
    df = load_dataset(cfg)
    parts = {name: df[df['split'] == name] for name in ['train', 'val', 'test']}
    for name, part in parts.items():
        print(f'{name:5s} {len(part):6d} orders, late rate {part[TARGET_COLUMN].mean():.3f}')

    pipeline = build_pipeline(
        cfg['best_params'],
        seller_k=cfg['seller_k'],
        min_category_freq=cfg['min_category_freq'],
        seed=cfg['seed'],
    )
    train_df = parts['train']
    pipeline.fit(train_df[list(INPUT_COLUMNS)], train_df[TARGET_COLUMN])

    metrics = {}
    for name in ['val', 'test']:
        part = parts[name]
        p_late = pipeline.predict_proba(part[list(INPUT_COLUMNS)])[:, 1]
        metrics[name] = evaluate(part[TARGET_COLUMN], p_late, cfg['threshold'])
    return pipeline, metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='config.yaml')
    args = parser.parse_args()

    started = time.perf_counter()
    cfg = load_config(args.config)
    pipeline, metrics = train(cfg)

    model_path = Path(cfg['paths']['model'])
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, model_path)
    (model_path.parent / 'metrics.json').write_text(json.dumps(metrics, indent=2))

    log_experiment(args.config, str(model_path.parent / 'metrics.json'), str(model_path))

    for name, values in metrics.items():
        print(f'{name:5s} ' + '  '.join(f'{k}={v:.3f}' for k, v in values.items()))
    print(f'saved {model_path} in {time.perf_counter() - started:.1f}s')


if __name__ == '__main__':
    main()
