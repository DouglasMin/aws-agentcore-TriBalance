# TriBalance Proxy

Lambda Function URL that sits between the TriBalance frontend and the AgentCore
Runtime. Three responsibilities:

1. **`POST /invoke`** — forward a user invocation to the AgentCore agent and
   stream SSE events back to the browser. Uses `RESPONSE_STREAM` Function URL
   invoke mode; the handler yields `data: {json}\n\n` frames from a
   boto3 `invoke_agent_runtime` streaming response.
2. **`POST /upload-url`** — mint a presigned PUT URL (5-min TTL) for direct-
   to-S3 upload of the Apple Health XML. Body: `{filename?, content_type?}`.
   Key layout: `samples/{run_id}/{filename}` under `INPUT_BUCKET`.
3. **`GET /artifact?key=...`** — mint a presigned GET URL for chart artifacts
   under `ARTIFACTS_BUCKET`. Key must start with `runs/` (traversal-safe).
   Currently unused by the recharts frontend but kept for future "view raw
   PNG" links.

## Stack

- AWS CDK (Python)
- Lambda Python 3.12 runtime
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
# 16 passed: stack synth + SSE invoke (5) + presign (10)
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
