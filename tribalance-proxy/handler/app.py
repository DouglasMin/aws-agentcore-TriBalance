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

from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from handler.invoke import stream_invoke_sse
from handler.presign import mint_artifact_url_fastapi, mint_upload_url_fastapi

app = FastAPI(title="TriBalance Proxy", docs_url=None, redoc_url=None)

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

    async def event_stream() -> AsyncGenerator[bytes, None]:
        for chunk in stream_invoke_sse(body):
            yield chunk

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
