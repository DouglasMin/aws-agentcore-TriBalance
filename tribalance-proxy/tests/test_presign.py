from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("BEDROCK_REGION", "ap-northeast-2")
    monkeypatch.setenv("INPUT_BUCKET", "tribalance-input")
    monkeypatch.setenv("ARTIFACTS_BUCKET", "tribalance-artifacts")
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:5173")


def _event(body=None, qs=None, origin="http://localhost:5173", method="POST", path="/upload-url"):
    e: dict = {
        "headers": {"origin": origin},
        "requestContext": {"http": {"method": method, "path": path}},
    }
    if body is not None:
        e["body"] = body if isinstance(body, str) else json.dumps(body)
    if qs is not None:
        e["queryStringParameters"] = qs
    return e


# -------- /upload-url --------

def test_upload_url_success():
    with patch("handler.presign.boto3.client") as mk_boto:
        client = MagicMock()
        client.generate_presigned_url.return_value = "https://signed.example/foo"
        mk_boto.return_value = client

        from handler.presign import mint_upload_url
        resp = mint_upload_url(_event({"filename": "export.xml"}))

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["url"] == "https://signed.example/foo"
    assert body["key"].startswith("uploads/") and body["key"].endswith("/export.xml")
    assert body["expires_in"] == 300

    call = client.generate_presigned_url.call_args
    assert call.kwargs["ClientMethod"] == "put_object"
    assert call.kwargs["Params"]["Bucket"] == "tribalance-input"
    assert call.kwargs["Params"]["ContentType"] == "application/xml"


def test_upload_url_default_filename():
    with patch("handler.presign.boto3.client") as mk_boto:
        client = MagicMock()
        client.generate_presigned_url.return_value = "https://signed.example/foo"
        mk_boto.return_value = client

        from handler.presign import mint_upload_url
        resp = mint_upload_url(_event({}))

    body = json.loads(resp["body"])
    assert body["key"].startswith("uploads/") and body["key"].endswith(".xml")


def test_upload_url_rejects_bad_filename():
    from handler.presign import mint_upload_url
    resp = mint_upload_url(_event({"filename": "../evil.xml"}))
    assert resp["statusCode"] == 400


def test_upload_url_invalid_json():
    from handler.presign import mint_upload_url
    resp = mint_upload_url(_event("not-json{{"))
    assert resp["statusCode"] == 400


# -------- /artifact --------

def test_artifact_url_success():
    with patch("handler.presign.boto3.client") as mk_boto:
        client = MagicMock()
        client.generate_presigned_url.return_value = "https://signed.example/bar"
        mk_boto.return_value = client

        from handler.presign import mint_artifact_url
        resp = mint_artifact_url(
            _event(qs={"key": "runs/abc/sleep_trend.png"}, method="GET", path="/artifact")
        )

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["url"] == "https://signed.example/bar"
    assert body["key"] == "runs/abc/sleep_trend.png"


def test_artifact_url_missing_key():
    from handler.presign import mint_artifact_url
    resp = mint_artifact_url(_event(qs={}, method="GET", path="/artifact"))
    assert resp["statusCode"] == 400


def test_artifact_url_rejects_traversal():
    from handler.presign import mint_artifact_url
    for bad in ["../secret", "/absolute/path", "runs/../etc"]:
        resp = mint_artifact_url(_event(qs={"key": bad}, method="GET", path="/artifact"))
        assert resp["statusCode"] in (400, 403), f"bad key accepted: {bad}"


def test_artifact_url_rejects_outside_runs_prefix():
    from handler.presign import mint_artifact_url
    resp = mint_artifact_url(_event(qs={"key": "config/secret.json"}, method="GET", path="/artifact"))
    assert resp["statusCode"] == 403


# -------- CORS --------

def test_upload_url_echoes_allowed_origin():
    with patch("handler.presign.boto3.client") as mk_boto:
        mk_boto.return_value.generate_presigned_url.return_value = "https://x"
        from handler.presign import mint_upload_url
        resp = mint_upload_url(_event({"filename": "x.xml"}, origin="http://localhost:5173"))
    assert resp["headers"]["Access-Control-Allow-Origin"] == "http://localhost:5173"


def test_upload_url_falls_back_for_unknown_origin():
    with patch("handler.presign.boto3.client") as mk_boto:
        mk_boto.return_value.generate_presigned_url.return_value = "https://x"
        from handler.presign import mint_upload_url
        resp = mint_upload_url(_event({"filename": "x.xml"}, origin="https://evil.com"))
    # Falls back to first allowlist entry, never wildcard
    assert resp["headers"]["Access-Control-Allow-Origin"] == "http://localhost:5173"
