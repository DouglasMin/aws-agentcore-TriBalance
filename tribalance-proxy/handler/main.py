"""TriBalance proxy Lambda — Function URL entrypoint.

Routes:
  POST /invoke          → stream SSE from AgentCore agent (P-02)
  POST /upload-url      → mint presigned PUT URL for input bucket (P-03)
  GET  /artifact?key=.. → mint presigned GET URL for artifact (P-03, may be dropped)

This file is the response-streaming entrypoint registered in CDK. Actual route
handlers live in invoke.py / presign.py.
"""

from __future__ import annotations

import json


def handler(event, context):
    """Non-streaming fallback (used when Function URL is invoked without streaming).

    Lambda Function URL with RESPONSE_STREAM invoke mode calls `lambda_handler`
    (response-streaming) when available; this sync handler is the plain-invoke
    fallback used for routing that doesn't need streaming (upload-url, artifact).
    """
    path = _path(event)
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")

    if method == "OPTIONS":
        return _cors_preflight()

    # Scaffolded routes — actual logic lands in P-02 / P-03.
    if path == "/invoke":
        return _stub("invoke streaming not wired yet (P-02)")
    if path == "/upload-url":
        return _stub("upload-url not wired yet (P-03)")
    if path == "/artifact":
        return _stub("artifact not wired yet (P-03)")

    return {"statusCode": 404, "body": json.dumps({"error": f"no route: {path}"})}


def _path(event: dict) -> str:
    return event.get("rawPath") or event.get("requestContext", {}).get("http", {}).get("path", "/")


def _stub(msg: str) -> dict:
    return {
        "statusCode": 501,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
        "body": json.dumps({"status": "scaffolded", "message": msg}),
    }


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
