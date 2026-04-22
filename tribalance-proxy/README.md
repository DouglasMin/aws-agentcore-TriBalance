# TriBalance Proxy

Lambda Function URL that sits between the TriBalance frontend and the AgentCore
Runtime. Uses **Lambda Web Adapter (LWA)** + **FastAPI** for true real-time SSE
streaming.

## Architecture

```
Browser (fetch + ReadableStream)
  │
  ▼  POST /invoke
Lambda Function URL (RESPONSE_STREAM)
  │
  ▼
Lambda Web Adapter (LWA layer)
  │  forwards HTTP to localhost:8080
  ▼
FastAPI / uvicorn (handler/app.py)
  │
  ├─ POST /invoke     → StreamingResponse(SSE) ← AgentCore Runtime
  ├─ POST /upload-url  → presigned PUT URL (S3)
  ├─ GET  /artifact    → presigned GET URL (S3)
  └─ GET  /health      → 200 OK (LWA readiness check)
```

**Why LWA?** Python Lambda managed runtime cannot natively stream generator
responses (only Node.js supports `RESPONSE_STREAM` natively). LWA runs a real
HTTP server (uvicorn) inside Lambda and proxies the Function URL request to it,
enabling FastAPI's `StreamingResponse` to yield SSE frames in real time.

## Stack

- AWS CDK (Python)
- Lambda Python 3.12 runtime
- Lambda Web Adapter v1.0.0 layer (x86_64)
- FastAPI + uvicorn (deps layer, built at synth time)
- Function URL, `AuthType=NONE`, `InvokeMode=RESPONSE_STREAM`, CORS for localhost
- Region: `ap-northeast-2`, Account: `612529367436`

## Dev

Setup:
```bash
cd tribalance-proxy
uv sync --extra dev
```

Tests:
```bash
uv run pytest -q
# 23 passed: FastAPI app (7) + SSE invoke (5) + presign (10) + stack synth (1)
```

Synth (no deploy, just render CloudFormation):
```bash
uv run cdk synth
```

Deploy (after bootstrap):
```bash
AWS_PROFILE=developer-dongik uv run cdk deploy
```

First-time CDK bootstrap (once per account/region):
```bash
AWS_PROFILE=developer-dongik uv run cdk bootstrap aws://612529367436/ap-northeast-2
```

## Outputs

After deploy:
- `ProxyFunctionUrl` — paste into frontend `VITE_PROXY_URL`
- `ProxyFunctionArn` — for IAM cross-references
