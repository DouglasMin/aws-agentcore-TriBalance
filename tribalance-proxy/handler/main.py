"""TriBalance proxy Lambda — legacy entrypoint (kept for reference).

With Lambda Web Adapter, the actual entrypoint is ``handler/app.py`` (FastAPI)
started by ``handler/run.sh``. This module is no longer used as the Lambda
handler but is preserved so existing tests that import from it still work.

If you need to test the old Lambda-event-dict interface, use
``handler.invoke.stream_invoke`` and ``handler.presign.mint_upload_url``
directly.
"""

from __future__ import annotations

import json

from handler.cors import cors_origin
from handler.invoke import stream_invoke
from handler.presign import mint_artifact_url, mint_upload_url


def lambda_handler(event, context=None):
    """Legacy handler — not used with LWA but kept for backward compat."""
    path = _path(event)
    method = _method(event)

    if method == "OPTIONS":
        return _cors_preflight(event)

    if path == "/invoke" and method == "POST":
        # Buffer mode fallback: collect all SSE frames into a single response.
        # This avoids the generator-not-serializable error if someone deploys
        # without LWA.
        frames = list(stream_invoke(event))
        body = b"".join(frames)
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Access-Control-Allow-Origin": cors_origin(event),
            },
            "body": body.decode("utf-8"),
            "isBase64Encoded": False,
        }

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
            "Access-Control-Allow-Origin": cors_origin(event),
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
            "Access-Control-Allow-Origin": cors_origin(event),
        },
        "body": json.dumps({"error": f"no route: {path}"}),
    }
