"""CORS helper — shared between main.py and presign.py.

Function URL's built-in CORS handles the OPTIONS preflight, but non-OPTIONS
responses rely on the ``Access-Control-Allow-Origin`` header from the Lambda
response body. We echo the request Origin when it's in the allowlist, and
fall back to the first allowlist entry otherwise — never a wildcard.
"""

from __future__ import annotations

import os


def _allowed_origins() -> list[str]:
    # Read every call so tests can monkeypatch ALLOWED_ORIGINS.
    return os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(",")


def cors_origin(event: dict) -> str:
    origins = _allowed_origins()
    origin = (event.get("headers") or {}).get("origin", "")
    return origin if origin in origins else origins[0]
