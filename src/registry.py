"""Moves the champion / challenger aliases of the registered model.

    python -m src.registry challenger 2
    python -m src.registry promote 2
    python -m src.registry rollback
    python -m src.registry show
"""
import argparse

from mlflow import MlflowClient
from mlflow.exceptions import MlflowException

from src.mlflow_config import MODEL_NAME, TRACKING_URI


def _client():
    return MlflowClient(tracking_uri=TRACKING_URI)


def _version_of(client, alias):
    """Version the alias points to, or None if the alias is not set."""
    try:
        return str(client.get_model_version_by_alias(MODEL_NAME, alias).version)
    except MlflowException:
        return None


def promote(version):
    """Makes `version` the champion and remembers the old champion as `previous`."""
    client = _client()
    version = str(version)
    current = _version_of(client, 'champion')

    if current == version:
        print(f'v{version} is already champion, nothing to do')
        return

    # Fails here (MlflowException) if the version does not exist, before any alias moves.
    client.get_model_version(MODEL_NAME, version)

    if current is not None:
        client.set_registered_model_alias(MODEL_NAME, 'previous', current)
    client.set_registered_model_alias(MODEL_NAME, 'champion', version)
    print(f'champion: {"-" if current is None else "v" + current} -> v{version}')


def set_challenger(version):
    client = _client()
    client.get_model_version(MODEL_NAME, str(version))
    client.set_registered_model_alias(MODEL_NAME, 'challenger', str(version))
    print(f'challenger: v{version}')


def rollback():
    """Swaps champion and previous, so a second rollback undoes the first."""
    client = _client()
    previous = _version_of(client, 'previous')
    current = _version_of(client, 'champion')

    if previous is None:
        raise RuntimeError('No previous version to roll back to')

    client.set_registered_model_alias(MODEL_NAME, 'champion', previous)
    client.set_registered_model_alias(MODEL_NAME, 'previous', current)
    print(f'champion: v{current} -> v{previous}')


def show():
    client = _client()
    for alias in ['champion', 'challenger', 'previous']:
        version = _version_of(client, alias)
        print(f'{alias:10s} {"-" if version is None else "v" + version}')


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('promote').add_argument('version')
    commands.add_parser('challenger').add_argument('version')
    commands.add_parser('rollback')
    commands.add_parser('show')
    args = parser.parse_args()

    if args.command == 'promote':
        promote(args.version)
    elif args.command == 'challenger':
        set_challenger(args.version)
    elif args.command == 'rollback':
        rollback()
    else:
        show()


if __name__ == '__main__':
    main()
