import src.batch_scoring as bs


class FakeS3:
    def __init__(self):
        self.uploads = []

    def upload_file(self, filename, bucket, key):
        self.uploads.append((filename, bucket, key))


def test_no_bucket_skips_upload(monkeypatch, tmp_path):
    monkeypatch.delenv('PREDICTIONS_BUCKET', raising=False)
    monkeypatch.setattr(bs.boto3, 'client', lambda name: 1 / 0)  # must not be called

    assert bs.upload_predictions(tmp_path / '2018-05.parquet', '2018-05') is None


def test_bucket_set_uploads_to_month_key(monkeypatch, tmp_path):
    s3 = FakeS3()
    monkeypatch.setenv('PREDICTIONS_BUCKET', 'my-bucket')
    monkeypatch.setattr(bs.boto3, 'client', lambda name: s3)
    path = tmp_path / '2018-05.parquet'

    uri = bs.upload_predictions(path, '2018-05')

    assert uri == 's3://my-bucket/predictions/2018-05.parquet'
    assert s3.uploads == [(str(path), 'my-bucket', 'predictions/2018-05.parquet')]
