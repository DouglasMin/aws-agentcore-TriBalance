"""Stream AgentCore Runtime invocation as SSE to the client.

Two entry points:
  - ``stream_invoke(event)`` — legacy Lambda event dict (kept for tests)
  - ``stream_invoke_sse(body)`` — FastAPI route: takes parsed JSON body directly

Architecture:
  1. Parse incoming POST JSON body (same payload shape the agent expects:
     {"s3_key": "...", "week_start": "..."}).
  2. Call bedrock-agentcore.invoke_agent_runtime(agentRuntimeArn, payload).
  3. The boto3 response is a streaming body of JSON-line events.
  4. Transform each line into SSE format:  `data: {json}\n\n`
  5. Yield bytes to the streaming response.

The frontend consumes with fetch() + ReadableStream + TextDecoder and parses
each `data: ...` chunk.
"""

from __future__ import annotations

import json
import os
from typing import Generator

import boto3


def _region() -> str:
    return os.environ.get("BEDROCK_REGION", "ap-northeast-2")


def _agent_arn() -> str:
    return os.environ["AGENTCORE_AGENT_ARN"]


def stream_invoke_sse(body: dict) -> Generator[bytes, None, None]:
    """Generator that yields SSE-formatted bytes.

    Called by the FastAPI route. Takes the already-parsed request body.
    """
    # Required field validation
    if not body.get("s3_key"):
        yield _sse({
            "event": "error",
            "kind": "invalid_input",
            "message": "payload.s3_key is required",
        })
        return

    # Invoke the AgentCore Runtime
    try:
        client = boto3.client("bedrock-agentcore", region_name=_region())
        resp = client.invoke_agent_runtime(
            agentRuntimeArn=_agent_arn(),
            payload=json.dumps(body).encode("utf-8"),
        )
    except Exception as e:
        yield _sse({
            "event": "error",
            "kind": "agentcore_invoke_failed",
            "message": f"invoke failed: {e}",
        })
        return

    # resp["response"] is a StreamingBody of \n-delimited JSON event chunks
    stream = resp.get("response")
    if stream is None:
        yield _sse({
            "event": "error",
            "kind": "agentcore_no_stream",
            "message": "no response stream from AgentCore",
        })
        return

    # NOTE: boto3 `StreamingBody.iter_chunks(N)` blocks until N bytes are
    # buffered OR EOF — this batches many events together. We want to forward
    # each event as soon as AgentCore emits it, so we reach into the urllib3
    # raw stream and use `read1()`, which returns whatever's currently in the
    # socket buffer without waiting for a fixed byte count.
    raw = getattr(stream, "_raw_stream", None)
    buffer = b""
    try:
        if raw is not None and hasattr(raw, "read1"):
            while True:
                chunk = raw.read1(65536)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    yield _sse(_parse_line(line))
        else:
            # Fallback: iter_chunks with a small size so events aren't
            # batched much. Not ideal but works if _raw_stream is gone.
            for chunk in stream.iter_chunks(chunk_size=64):
                if not chunk:
                    continue
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    yield _sse(_parse_line(line))

        # Flush trailing partial line (no newline terminator)
        tail = buffer.strip()
        if tail:
            yield _sse(_parse_line(tail))
    except GeneratorExit:
        # Client disconnected (fetch.abort() on the browser side). FastAPI
        # sends GeneratorExit into this generator on the next yield. Close
        # the underlying HTTP connection to AgentCore so the service sees
        # our disconnect and can short-circuit its own work. Re-raise so
        # the framework knows we acknowledged the close.
        raise
    except Exception as e:
        yield _sse({
            "event": "error",
            "kind": "stream_drop",
            "message": f"stream read failed: {e}",
        })
        return
    finally:
        # Always close the boto3 StreamingBody whether we finished, errored,
        # or got aborted — frees the urllib3 socket and lets the connection
        # pool reuse it (otherwise we leak one open HTTP conn per invocation).
        try:
            stream.close()
        except Exception:
            pass


def stream_invoke(event: dict) -> Generator[bytes, None, None]:
    """Legacy Lambda event-dict entry point (used by tests and old handler).

    Parses the body from the Lambda event and delegates to stream_invoke_sse.
    """
    try:
        raw = event.get("body") or "{}"
        body = json.loads(raw)
    except json.JSONDecodeError:
        yield _sse({
            "event": "error",
            "kind": "invalid_input",
            "message": "invalid JSON body",
        })
        return

    yield from stream_invoke_sse(body)


def _parse_line(line: bytes) -> dict:
    """Decode a single line from the AgentCore stream.

    AgentCore may emit lines in two formats:
      - SSE-wrapped: ``data: {"event": ...}``  (with ``data: `` prefix)
      - Raw JSON:    ``{"event": ...}``

    We strip the ``data: `` prefix if present, then JSON-parse.
    """
    text = line.decode("utf-8", errors="replace")
    # Strip SSE prefix if the AgentCore stream is already SSE-formatted
    if text.startswith("data: "):
        text = text[6:]
    elif text.startswith("data:"):
        text = text[5:]
    text = text.strip()
    if not text:
        return {"event": "raw", "data": ""}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"event": "raw", "data": text}


def _sse(obj: dict) -> bytes:
    """Encode a single event object as SSE ``data:`` line."""
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n".encode("utf-8")
