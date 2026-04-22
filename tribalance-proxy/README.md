# TriBalance Proxy

Lambda Function URL that sits between the TriBalance frontend and the AgentCore
Runtime. Three responsibilities:

1. **`POST /invoke`** — forward a user invocation to the AgentCore agent and
   stream SSE events back to the browser. (Wired in P-02.)
2. **`POST /upload-url`** — mint a presigned PUT URL for direct-to-S3 uploads
   of the Apple Health XML. (Wired in P-03.)
3. **`GET /artifact?key=...`** — mint a presigned GET URL for chart artifacts
   (currently unused by the frontend since recharts replaced matplotlib PNGs;
   kept for future).

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
