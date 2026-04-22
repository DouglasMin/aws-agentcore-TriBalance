"""S3 presigned URL endpoints.

Two routes:
  POST /upload-url         — client wants to upload an Apple Health XML
  GET  /artifact?key=...   — client wants to read a chart artifact

Both return a short-TTL (5 min) presigned URL the browser can hit directly —
browser-to-S3 traffic bypasses Lambda, so a 100 MB+ XML never transits us.

Two entry-point styles per route:
  - ``mint_upload_url(event)`` / ``mint_artifact_url(event)`` — legacy Lambda
    event dict (kept for backward compat and tests)
  - ``mint_upload_url_fastapi(body)`` / ``mint_artifact_url_fastapi(key)`` —
    FastAPI route helpers that return ``{"status": int, "body": dict}``
"""

from __future__ import annotations

import json
import os
import re
import uuid

import boto3
from botocore.client import Config

from handler.cors import cors_origin

_TTL_SEC = 300  # 5 minutes

_FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._/-]+$")


def _region() -> str:
    return os.environ.get("BEDROCK_REGION", "ap-northeast-2")


def _input_bucket() -> str:
    return os.environ.get("INPUT_BUCKET", "tribalance-input")


def _artifacts_bucket() -> str:
    return os.environ.get("ARTIFACTS_BUCKET", "tribalance-artifacts")


def _s3_client():
    return boto3.client(
        "s3",
        region_name=_region(),
        config=Config(signature_version="s3v4"),
    )


# ---------------------------------------------------------------------------
# Legacy Lambda event-dict entry points (kept for tests)
# ---------------------------------------------------------------------------

def _json_response(event: dict, status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": cors_origin(event),
        },
        "body": json.dumps(body),
    }


def mint_upload_url(event: dict) -> dict:
    """POST /upload-url — body: {filename?, content_type?} → presigned PUT URL."""
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _json_response(event, 400, {"error": "invalid JSON body"})

    result = _do_mint_upload(body)
    return _json_response(event, result["status"], result["body"])


def mint_artifact_url(event: dict) -> dict:
    """GET /artifact?key=... — presigned GET URL under ARTIFACTS_BUCKET."""
    qs = event.get("queryStringParameters") or {}
    key = qs.get("key", "")
    result = _do_mint_artifact(key)
    return _json_response(event, result["status"], result["body"])


# ---------------------------------------------------------------------------
# FastAPI entry points
# ---------------------------------------------------------------------------

def mint_upload_url_fastapi(body: dict) -> dict:
    """FastAPI route helper. Returns {"status": int, "body": dict}."""
    return _do_mint_upload(body)


def mint_artifact_url_fastapi(key: str) -> dict:
    """FastAPI route helper. Returns {"status": int, "body": dict}."""
    return _do_mint_artifact(key)


# ---------------------------------------------------------------------------
# Shared implementation
# ---------------------------------------------------------------------------

def _do_mint_upload(body: dict) -> dict:
    filename = body.get("filename") or f"upload_{uuid.uuid4().hex[:8]}.xml"
    content_type = body.get("content_type") or "application/xml"

    if not _FILENAME_PATTERN.match(filename):
        return {
            "status": 400,
            "body": {"error": "filename must match [A-Za-z0-9._-]+"},
        }

    run_id = uuid.uuid4().hex[:12]
    key = f"samples/{run_id}/{filename}"

    try:
        url = _s3_client().generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": _input_bucket(),
                "Key": key,
                "ContentType": content_type,
            },
            ExpiresIn=_TTL_SEC,
            HttpMethod="PUT",
        )
    except Exception as e:
        return {"status": 500, "body": {"error": f"presign failed: {e}"}}

    return {
        "status": 200,
        "body": {"url": url, "key": key, "expires_in": _TTL_SEC},
    }


def _do_mint_artifact(key: str) -> dict:
    if not key:
        return {"status": 400, "body": {"error": "query param 'key' is required"}}

    if key.startswith("/") or ".." in key or not _KEY_PATTERN.match(key):
        return {"status": 400, "body": {"error": f"invalid key: {key}"}}
    if not key.startswith("runs/"):
        return {"status": 403, "body": {"error": "key must be under runs/"}}

    try:
        url = _s3_client().generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": _artifacts_bucket(), "Key": key},
            ExpiresIn=_TTL_SEC,
            HttpMethod="GET",
        )
    except Exception as e:
        return {"status": 500, "body": {"error": f"presign failed: {e}"}}

    return {
        "status": 200,
        "body": {"url": url, "key": key, "expires_in": _TTL_SEC},
    }
