"""S3 presigned URL endpoints.

Two routes:
  POST /upload-url         — client wants to upload an Apple Health XML
  GET  /artifact?key=...   — client wants to read a chart artifact (unused by
                             the recharts frontend but kept for future).

Both return a short-TTL (5 min) presigned URL the browser can hit directly —
browser-to-S3 traffic bypasses Lambda, so a 100 MB+ XML never transits us.
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
    # signature_version='s3v4' is required for non-us-east-1 buckets with
    # presigned URLs.
    return boto3.client(
        "s3",
        region_name=_region(),
        config=Config(signature_version="s3v4"),
    )


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

    filename = body.get("filename") or f"upload_{uuid.uuid4().hex[:8]}.xml"
    content_type = body.get("content_type") or "application/xml"

    if not _FILENAME_PATTERN.match(filename):
        return _json_response(
            event,
            400,
            {"error": "filename must match [A-Za-z0-9._-]+"},
        )

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
    except Exception as e:  # noqa: BLE001 — return details to client
        return _json_response(event, 500, {"error": f"presign failed: {e}"})

    return _json_response(
        event,
        200,
        {"url": url, "key": key, "expires_in": _TTL_SEC},
    )


def mint_artifact_url(event: dict) -> dict:
    """GET /artifact?key=... — presigned GET URL under ARTIFACTS_BUCKET.

    Security: key must start with ``runs/`` and match the safe charset
    (no path-traversal, no absolute paths).
    """
    qs = event.get("queryStringParameters") or {}
    key = qs.get("key")

    if not key:
        return _json_response(event, 400, {"error": "query param 'key' is required"})

    if key.startswith("/") or ".." in key or not _KEY_PATTERN.match(key):
        return _json_response(event, 400, {"error": f"invalid key: {key}"})
    if not key.startswith("runs/"):
        return _json_response(event, 403, {"error": "key must be under runs/"})

    try:
        url = _s3_client().generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": _artifacts_bucket(), "Key": key},
            ExpiresIn=_TTL_SEC,
            HttpMethod="GET",
        )
    except Exception as e:  # noqa: BLE001
        return _json_response(event, 500, {"error": f"presign failed: {e}"})

    return _json_response(
        event,
        200,
        {"url": url, "key": key, "expires_in": _TTL_SEC},
    )
