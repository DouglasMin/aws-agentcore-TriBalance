"""FastAPI application for the TriBalance proxy Lambda.

Replaces the old plain-dict Lambda handler with a proper ASGI app so that
Lambda Web Adapter (LWA) can stream SSE responses in real time.

Routes:
  POST /invoke          → StreamingResponse of SSE from AgentCore agent
  POST /upload-url      → JSON: presigned PUT URL for input bucket
  GET  /artifact        → JSON: presigned GET URL for artifact
  GET  /health          → 200 OK (LWA readiness check)
"""

from __future__ import annotations

import os
from typing import AsyncGenerator, Optional

import boto3
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from handler.invoke import stream_invoke_sse
from handler.presign import mint_artifact_url_fastapi, mint_upload_url_fastapi

app = FastAPI(title="TriBalance Proxy", docs_url=None, redoc_url=None)


# --------------------------------------------------------------------------
# Auth — shared Bearer token via Secrets Manager. Cached at module level so
# cold start pays the fetch cost once; warm invocations hit memory.
# If APP_TOKEN_SECRET_ARN isn't set (local dev), auth is disabled.
# --------------------------------------------------------------------------
_AUTH_EXEMPT_PATHS = frozenset({"/health"})
_token_cache: Optional[str] = None
_token_fetched = False


def _app_token() -> Optional[str]:
    global _token_cache, _token_fetched
    if _token_fetched:
        return _token_cache
    arn = os.environ.get("APP_TOKEN_SECRET_ARN")
    if not arn:
        _token_fetched = True
        return None
    try:
        client = boto3.client(
            "secretsmanager",
            region_name=os.environ.get("BEDROCK_REGION", "ap-northeast-2"),
        )
        resp = client.get_secret_value(SecretId=arn)
        _token_cache = resp.get("SecretString")
    except Exception:
        # On fetch failure, leave cache unset so we can retry on next call
        # instead of permanently locking out all requests. Return None to
        # "fail open" for now; harden to "fail closed" if this becomes risky.
        return None
    _token_fetched = True
    return _token_cache


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if request.url.path in _AUTH_EXEMPT_PATHS:
        return await call_next(request)
    token = _app_token()
    if token is None:
        # Auth disabled (no secret configured)
        return await call_next(request)
    header = request.headers.get("authorization", "")
    supplied = header[7:] if header.startswith("Bearer ") else ""
    if supplied != token:
        return JSONResponse(
            {"error": "unauthorized", "kind": "unauthorized"},
            status_code=401,
        )
    return await call_next(request)

# CORS is handled by the Lambda Function URL configuration (CDK stack).
# Do NOT add CORSMiddleware here — it would duplicate the
# Access-Control-Allow-Origin header and browsers reject that.


@app.get("/health")
async def health():
    """LWA readiness check endpoint."""
    return {"status": "ok"}


@app.post("/invoke")
async def invoke(request: Request):
    """Stream SSE events from AgentCore Runtime invocation."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    # Wrap the sync generator so that when the client disconnects and FastAPI
    # closes this async generator, we explicitly close the inner sync
    # generator — that fires its `finally` block which closes the boto3
    # stream (see handler/invoke.py). Without the explicit close, the for-
    # loop just exits and the underlying urllib3 socket leaks.
    gen = stream_invoke_sse(body)

    async def event_stream() -> AsyncGenerator[bytes, None]:
        try:
            for chunk in gen:
                yield chunk
        finally:
            gen.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/upload-url")
async def upload_url(request: Request):
    """Mint a presigned PUT URL for direct-to-S3 upload."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    result = mint_upload_url_fastapi(body)
    return JSONResponse(content=result["body"], status_code=result["status"])


@app.get("/artifact")
async def artifact(key: str = ""):
    """Mint a presigned GET URL for chart artifacts."""
    result = mint_artifact_url_fastapi(key)
    return JSONResponse(content=result["body"], status_code=result["status"])
