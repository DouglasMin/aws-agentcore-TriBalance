from pathlib import Path
from unittest.mock import MagicMock

from nodes.fetch import make_fetch_node


def test_fetch_downloads_to_temp_and_updates_state(tmp_path, monkeypatch):
    s3 = MagicMock()

    def _fake_download(bucket, key, dest):
        Path(dest).write_bytes(b"<HealthData/>")

    s3.download.side_effect = _fake_download

    monkeypatch.setenv("INPUT_S3_BUCKET", "bucket-x")
    node = make_fetch_node(s3=s3, tmp_root=tmp_path)

    state = {"s3_key": "samples/foo.xml"}
    result = node(state)

    s3.download.assert_called_once()
    call = s3.download.call_args
    assert call.args[0] == "bucket-x"
    assert call.args[1] == "samples/foo.xml"
    local = Path(result["local_xml_path"])
    assert local.exists()
    assert local.read_bytes() == b"<HealthData/>"


def test_fetch_raises_on_missing_s3_key(tmp_path):
    node = make_fetch_node(s3=MagicMock(), tmp_root=tmp_path)
    try:
        node({})
    except KeyError as e:
        assert "s3_key" in str(e)
    else:
        raise AssertionError("expected KeyError")
