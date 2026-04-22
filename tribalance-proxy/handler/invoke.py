"""Stream AgentCore Runtime invocation as SSE to the Lambda Function URL client.

Architecture:
  1. Parse incoming POST JSON body (it's the same payload shape the agent expects:
     {"s3_key": "...", "week_start": "..."}).
  2. Call bedrock-agentcore.invoke_agent_runtime(agentRuntimeArn, payload).
  3. The boto3 response is a streaming body of JSON-line events.
  4. Transform each line into SSE format:  `data: {json}\n\n`
  5. Yield bytes to the Function URL streaming response.

The frontend consumes with fetch() + ReadableStream + TextDecoder and parses
each `data: ...` chunk.
"""

from __future__ import annotations

import json
import os
from typing import Iterable

import boto3


def _region() -> str:
    return os.environ.get("BEDROCK_REGION", "ap-northeast-2")


def _agent_arn() -> str:
    return os.environ["AGENTCORE_AGENT_ARN"]


def stream_invoke(event: dict) -> Iterable[bytes]:
    """Generator that yields SSE-formatted bytes to the Function URL response stream.

    Lambda RESPONSE_STREAM mode consumes a generator of bytes and streams them to
    the HTTP client. CORS headers are provided by the Function URL configuration
    itself (not emitted in the body).

    Each chunk yielded here is a single SSE frame: ``data: {json}\n\n``.
    """
    # Parse request body
    try:
        raw = event.get("body") or "{}"
        body = json.loads(raw)
    except json.JSONDecodeError:
        yield _sse({"event": "error", "message": "invalid JSON body"})
        return

    # Required field validation
    if not body.get("s3_key"):
        yield _sse({"event": "error", "message": "payload.s3_key is required"})
        return

    # Invoke the AgentCore Runtime
    try:
        client = boto3.client("bedrock-agentcore", region_name=_region())
        resp = client.invoke_agent_runtime(
            agentRuntimeArn=_agent_arn(),
            payload=json.dumps(body).encode("utf-8"),
        )
    except Exception as e:
        yield _sse({"event": "error", "message": f"invoke failed: {e}"})
        return

    # resp["response"] is a StreamingBody of \n-delimited JSON event chunks
    # (AgentCore streams the @app.entrypoint yields as JSON lines).
    stream = resp.get("response")
    if stream is None:
        yield _sse({"event": "error", "message": "no response stream from AgentCore"})
        return

    buffer = b""
    try:
        for chunk in stream.iter_chunks(chunk_size=4096):
            if not chunk:
                continue
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                yield _sse(_parse_line(line))
    except Exception as e:
        yield _sse({"event": "error", "message": f"stream read failed: {e}"})
        return

    # Flush trailing partial line (no newline terminator)
    tail = buffer.strip()
    if tail:
        yield _sse(_parse_line(tail))


def _parse_line(line: bytes) -> dict:
    """Decode a single JSON-line event; fall back to raw wrapper if non-JSON."""
    try:
        return json.loads(line.decode("utf-8"))
    except json.JSONDecodeError:
        return {"event": "raw", "data": line.decode("utf-8", errors="replace")}


def _sse(obj: dict) -> bytes:
    """Encode a single event object as SSE ``data:`` line."""
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n".encode("utf-8")
