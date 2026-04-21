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

## Deploy

```bash
AWS_PROFILE=developer-dongik agentcore launch
```
