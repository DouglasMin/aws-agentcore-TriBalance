# TriBalance Backend

AgentCore Runtime + Code Interpreter agent that analyzes Apple Health exports
and produces a weekly sleep+activity report with charts.

See design spec: `../docs/superpowers/specs/2026-04-21-tribalance-init-design.md`

## Quickstart

```bash
cd app/TriBalanceAgent
uv sync

# Back at tribalance/
./dev.sh
```

> Note: `dev.sh` and the Python package are created in subsequent tasks of the
> init plan. Until then, `uv sync` and `./dev.sh` will not work. Run the plan
> tasks first.

## Deploy

```bash
AWS_PROFILE=developer-dongik agentcore launch
```
