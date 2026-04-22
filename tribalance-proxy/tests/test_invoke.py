"""Unit test: stream_invoke generator produces correct SSE frames from a
faked AgentCore response."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("BEDROCK_REGION", "ap-northeast-2")
    monkeypatch.setenv(
        "AGENTCORE_AGENT_ARN",
        "arn:aws:bedrock-agentcore:ap-northeast-2:612529367436:runtime/TriBalanceAgent-jXn0PKFg4F",
    )
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:5173")


class _FakeStream:
    def __init__(self, lines: list[bytes]):
        self._lines = lines

    def iter_chunks(self, chunk_size=4096):
        # Emit one line per chunk (tests can exercise multi-line buffering too)
        for line in self._lines:
            yield line


def _event(body) -> dict:
    return {
        "rawPath": "/invoke",
        "requestContext": {"http": {"method": "POST", "path": "/invoke"}},
        "body": body if isinstance(body, str) else json.dumps(body),
    }


def test_stream_invoke_emits_run_started_and_complete(monkeypatch):
    """Real agent emits JSON lines like `{"event":"run_started",...}`.
    Our streamer should wrap each in `data: ...\n\n`."""

    # Prepare a fake AgentCore response
    fake_response = {
        "response": _FakeStream([
            b'{"event":"run_started","run_id":"abc"}\n',
            b'{"event":"node_end","node":"fetch"}\n',
            b'{"event":"complete","report":{"run_id":"abc"}}\n',
        ])
    }

    with patch("handler.invoke.boto3.client") as mk_boto:
        client = MagicMock()
        client.invoke_agent_runtime.return_value = fake_response
        mk_boto.return_value = client

        from handler.invoke import stream_invoke
        frames = list(stream_invoke(_event({"s3_key": "foo.xml"})))

    # 3 events -> 3 frames
    assert len(frames) == 3
    for frame in frames:
        assert frame.startswith(b"data: ")
        assert frame.endswith(b"\n\n")

    # First frame has run_started
    first = json.loads(frames[0][6:-2].decode("utf-8"))
    assert first["event"] == "run_started"
    assert first["run_id"] == "abc"

    # Invoke was called with the right ARN + payload
    client.invoke_agent_runtime.assert_called_once()
    call_kwargs = client.invoke_agent_runtime.call_args.kwargs
    assert "runtime/TriBalanceAgent-" in call_kwargs["agentRuntimeArn"]
    assert json.loads(call_kwargs["payload"]) == {"s3_key": "foo.xml"}


def test_stream_invoke_missing_s3_key_emits_error(monkeypatch):
    from handler.invoke import stream_invoke
    frames = list(stream_invoke(_event({})))  # no s3_key
    assert len(frames) == 1
    payload = json.loads(frames[0][6:-2])
    assert payload["event"] == "error"
    assert "s3_key" in payload["message"]


def test_stream_invoke_handles_multi_event_chunk(monkeypatch):
    """If AgentCore emits multiple JSON lines in a single TCP chunk, we still
    split on \\n and emit one SSE frame per event."""
    fake_response = {
        "response": _FakeStream([
            b'{"event":"a"}\n{"event":"b"}\n{"event":"c"}\n',
        ])
    }
    with patch("handler.invoke.boto3.client") as mk_boto:
        client = MagicMock()
        client.invoke_agent_runtime.return_value = fake_response
        mk_boto.return_value = client

        from handler.invoke import stream_invoke
        frames = list(stream_invoke(_event({"s3_key": "x"})))

    assert len(frames) == 3
    events = [json.loads(f[6:-2])["event"] for f in frames]
    assert events == ["a", "b", "c"]


def test_stream_invoke_handles_invoke_error(monkeypatch):
    """boto3 client raises (auth, service, etc) -> emit a single error frame."""
    with patch("handler.invoke.boto3.client") as mk_boto:
        client = MagicMock()
        client.invoke_agent_runtime.side_effect = RuntimeError("access denied")
        mk_boto.return_value = client

        from handler.invoke import stream_invoke
        frames = list(stream_invoke(_event({"s3_key": "x"})))

    assert len(frames) == 1
    payload = json.loads(frames[0][6:-2])
    assert payload["event"] == "error"
    assert "access denied" in payload["message"]


def test_stream_invoke_handles_invalid_json_body(monkeypatch):
    from handler.invoke import stream_invoke
    bad_event = _event("not-json{{")
    frames = list(stream_invoke(bad_event))
    assert len(frames) == 1
    payload = json.loads(frames[0][6:-2])
    assert payload["event"] == "error"
    assert "invalid JSON" in payload["message"].lower() or "JSON" in payload["message"]
