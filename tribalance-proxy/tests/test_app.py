"""Tests for the FastAPI app (handler/app.py).

Uses httpx + FastAPI TestClient to exercise the real ASGI app.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("BEDROCK_REGION", "ap-northeast-2")
    monkeypatch.setenv(
        "AGENTCORE_AGENT_ARN",
        "arn:aws:bedrock-agentcore:ap-northeast-2:612529367436:runtime/TriBalanceAgent-jXn0PKFg4F",
    )
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:5173")
    monkeypatch.setenv("INPUT_BUCKET", "tribalance-input")
    monkeypatch.setenv("ARTIFACTS_BUCKET", "tribalance-artifacts")


@pytest.fixture
def client():
    from handler.app import app
    return TestClient(app)


class _FakeStream:
    def __init__(self, lines: list[bytes]):
        self._lines = lines

    def iter_chunks(self, chunk_size=4096):
        for line in self._lines:
            yield line


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_invoke_streams_sse(client):
    fake_response = {
        "response": _FakeStream([
            b'{"event":"run_started","run_id":"abc"}\n',
            b'{"event":"node_end","node":"fetch"}\n',
            b'{"event":"complete","report":{"run_id":"abc"}}\n',
        ])
    }

    with patch("handler.invoke.boto3.client") as mk_boto:
        mk = MagicMock()
        mk.invoke_agent_runtime.return_value = fake_response
        mk_boto.return_value = mk

        resp = client.post(
            "/invoke",
            json={"s3_key": "foo.xml"},
        )

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    # Parse SSE frames
    frames = [
        line for line in resp.text.split("\n\n")
        if line.strip().startswith("data:")
    ]
    assert len(frames) == 3

    first = json.loads(frames[0].removeprefix("data: "))
    assert first["event"] == "run_started"
    assert first["run_id"] == "abc"


def test_invoke_missing_s3_key(client):
    resp = client.post("/invoke", json={})
    assert resp.status_code == 200  # SSE stream with error event
    assert "s3_key" in resp.text


def test_upload_url(client):
    with patch("handler.presign.boto3.client") as mk_boto:
        mk = MagicMock()
        mk.generate_presigned_url.return_value = "https://signed.example/foo"
        mk_boto.return_value = mk

        resp = client.post(
            "/upload-url",
            json={"filename": "export.xml"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["url"] == "https://signed.example/foo"
    assert body["key"].startswith("samples/")
    assert body["key"].endswith("/export.xml")


def test_artifact_url(client):
    with patch("handler.presign.boto3.client") as mk_boto:
        mk = MagicMock()
        mk.generate_presigned_url.return_value = "https://signed.example/bar"
        mk_boto.return_value = mk

        resp = client.get("/artifact", params={"key": "runs/abc/sleep_trend.png"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["url"] == "https://signed.example/bar"


def test_artifact_url_rejects_traversal(client):
    resp = client.get("/artifact", params={"key": "../secret"})
    assert resp.status_code == 400


def test_artifact_url_rejects_outside_runs(client):
    resp = client.get("/artifact", params={"key": "config/secret.json"})
    assert resp.status_code == 403
