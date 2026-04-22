"""S3 presigned URL endpoints.

Buffered (non-streaming) Lambda responses: return a dict that Lambda's Function
URL treats as a standard HTTP response. Actual implementation lands in P-03.
"""

from __future__ import annotations

import json


def mint_upload_url(event: dict) -> dict:
    """POST /upload-url — stub until P-03."""
    return {
        "statusCode": 501,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": "not wired yet (P-03)"}),
    }


def mint_artifact_url(event: dict) -> dict:
    """GET /artifact?key=... — stub until P-03."""
    return {
        "statusCode": 501,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": "not wired yet (P-03)"}),
    }
