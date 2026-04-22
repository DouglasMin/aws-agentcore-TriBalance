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

from handler.invoke import stream_invoke
from handler.presign import mint_artifact_url, mint_upload_url


def lambda_handler(event, context=None):
    """Streaming-capable entrypoint for the Lambda Function URL.

    Returns:
      - For ``POST /invoke``: a generator of bytes (SSE frames).
      - For other routes: a dict (buffered JSON response).
    """
    path = _path(event)
    method = _method(event)

    if method == "OPTIONS":
        return _cors_preflight()

    if path == "/invoke" and method == "POST":
        return stream_invoke(event)

    if path == "/upload-url" and method == "POST":
        return mint_upload_url(event)

    if path == "/artifact" and method == "GET":
        return mint_artifact_url(event)

    return _not_found(path)


# Expose as ``handler`` too so either CDK setting works:
#   handler="main.lambda_handler"  (preferred)
#   handler="main.handler"          (legacy P-01 value)
handler = lambda_handler


def _path(event: dict) -> str:
    return event.get("rawPath") or event.get("requestContext", {}).get("http", {}).get("path", "/")


def _method(event: dict) -> str:
    return event.get("requestContext", {}).get("http", {}).get("method", "GET")


def _cors_preflight() -> dict:
    return {
        "statusCode": 204,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Max-Age": "600",
        },
    }


def _not_found(path: str) -> dict:
    return {
        "statusCode": 404,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": f"no route: {path}"}),
    }
