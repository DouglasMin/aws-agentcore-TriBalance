"""TriBalance proxy Lambda — Function URL entrypoint.

Routes:
  POST /invoke          → stream SSE from AgentCore agent (P-02)
  POST /upload-url      → mint presigned PUT URL for input bucket (P-03)
  GET  /artifact?key=.. → mint presigned GET URL for artifact (P-03, may be dropped)

The ``lambda_handler`` function is the entrypoint. When the Function URL is
configured with ``InvokeMode=RESPONSE_STREAM``, the Lambda Python runtime
streams bytes from a generator return value directly to the HTTP client.
Non-streaming routes return a plain dict (buffered HTTP response).
"""

from __future__ import annotations

import json
import os

from handler.invoke import stream_invoke
from handler.presign import mint_artifact_url, mint_upload_url

_ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(",")


def _cors_origin(event: dict) -> str:
    """Pick the response Access-Control-Allow-Origin based on request Origin header
    matched against ALLOWED_ORIGINS env. Falls back to the first allowlist entry
    if no match (some browsers accept any string, but our list stays honest)."""
    origin = (event.get("headers") or {}).get("origin", "")
    return origin if origin in _ALLOWED_ORIGINS else _ALLOWED_ORIGINS[0]


def lambda_handler(event, context=None):
    """Streaming-capable entrypoint for the Lambda Function URL.

    Returns:
      - For ``POST /invoke``: a generator of bytes (SSE frames).
      - For other routes: a dict (buffered JSON response).
    """
    path = _path(event)
    method = _method(event)

    if method == "OPTIONS":
        return _cors_preflight(event)

    if path == "/invoke" and method == "POST":
        return stream_invoke(event)

    if path == "/upload-url" and method == "POST":
        return mint_upload_url(event)

    if path == "/artifact" and method == "GET":
        return mint_artifact_url(event)

    return _not_found(event, path)


def _path(event: dict) -> str:
    return event.get("rawPath") or event.get("requestContext", {}).get("http", {}).get("path", "/")


def _method(event: dict) -> str:
    return event.get("requestContext", {}).get("http", {}).get("method", "GET")


def _cors_preflight(event: dict) -> dict:
    return {
        "statusCode": 204,
        "headers": {
            "Access-Control-Allow-Origin": _cors_origin(event),
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Max-Age": "600",
        },
    }


def _not_found(event: dict, path: str) -> dict:
    return {
        "statusCode": 404,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": _cors_origin(event),
        },
        "body": json.dumps({"error": f"no route: {path}"}),
    }
