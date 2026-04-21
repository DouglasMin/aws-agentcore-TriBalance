from io import BytesIO
from unittest.mock import MagicMock

from infra.s3 import S3Client


def test_download_to_path(tmp_path, monkeypatch):
    mock_boto = MagicMock()
    body = BytesIO(b"<HealthData/>")
    mock_boto.get_object.return_value = {"Body": body}
    monkeypatch.setattr("infra.s3.boto3.client", lambda *_a, **_k: mock_boto)

    client = S3Client(region="us-west-2")
    dest = tmp_path / "sample.xml"
    client.download("bucket-x", "key/file.xml", dest)

    assert dest.read_bytes() == b"<HealthData/>"
    mock_boto.get_object.assert_called_once_with(Bucket="bucket-x", Key="key/file.xml")


def test_upload_bytes(monkeypatch):
    mock_boto = MagicMock()
    monkeypatch.setattr("infra.s3.boto3.client", lambda *_a, **_k: mock_boto)

    client = S3Client(region="us-west-2")
    client.upload_bytes("bucket-x", "runs/abc/chart.png", b"PNGDATA", content_type="image/png")

    mock_boto.put_object.assert_called_once_with(
        Bucket="bucket-x",
        Key="runs/abc/chart.png",
        Body=b"PNGDATA",
        ContentType="image/png",
    )
