# TriBalance Backend

AgentCore Runtime + Code Interpreter agent that analyzes Apple Health exports
and produces a weekly sleep+activity report with charts.

See design spec: `../docs/superpowers/specs/2026-04-21-tribalance-init-design.md`

## Setup (once)

```bash
# from this directory (tribalance/)
uv venv --python 3.13
source .venv/bin/activate
uv pip install -e "app/TriBalanceAgent[dev]"
uv pip install bedrock-agentcore-starter-toolkit   # provides `agentcore` CLI
```

The venv lives at `tribalance/.venv` (mirrors `finance-ai-app` pattern). The
Python `bedrock-agentcore-starter-toolkit` installs the `agentcore` CLI
(`launch`, `dev`, `invoke`, ...) into this venv — activating it shadows any
global `agentcore` binary on PATH so all project commands resolve to the
Python CLI.

The agent package itself is at `app/TriBalanceAgent/` with its own
`pyproject.toml`/`uv.lock`; we install it editable into the parent venv.

## Local dev

```bash
source .venv/bin/activate
./dev.sh
```

## Tests

```bash
source .venv/bin/activate
cd app/TriBalanceAgent
pytest -q
```

## Deploy

```bash
source .venv/bin/activate
AWS_PROFILE=developer-dongik agentcore launch
```

First launch creates `.bedrock_agentcore.yaml` in this directory.
(`deploy` is the newer alias for `launch` — either works.)
