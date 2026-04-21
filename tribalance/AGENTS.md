# TriBalance Backend — AgentCore Project

Apple Health → Code Interpreter-driven weekly health report agent.

## Status

This document describes the intended shape of the project. It is being built
task-by-task per `../docs/superpowers/plans/2026-04-21-tribalance-init.md`.
Some files listed below may not yet exist; check `git log` to see what has
landed.

## Mental Model

Schema-first AgentCore project. `agentcore/agentcore.json` is the source of truth;
`agentcore/cdk/` is auto-generated and must not be hand-edited.

Single runtime: `TriBalanceAgent` (Container build). LangGraph StateGraph with 6 linear
nodes. Code Interpreter (separate AgentCore managed sandbox) is invoked from two nodes
(`sleep`, `activity`) via the low-level `bedrock_agentcore.tools.code_interpreter_client`
SDK — no Strands adapter is used.

## Critical Invariants

1. **Don't edit `agentcore/cdk/`.** It is regenerated from `agentcore.json`.
2. **Nodes don't import nodes.** Nodes depend only on `infra/`, `state`, `events`.
3. **Prompts live in `prompts/*.md`.** Never hard-code a prompt in a `.py` file.
4. **Code Interpreter session is 1-per-invocation.** Always open with a `with` block.
5. **LLM provider switch via env only (this phase).** DynamoDB/Memory-driven runtime switching is deferred to Phase 2.

## Directory

```
agentcore/        AgentCore schema + (auto) CDK
app/              Runtime code (1 runtime = 1 app subdir)
  TriBalanceAgent/
    main.py       Entrypoint; @app.entrypoint
    graph.py      StateGraph assembly
    state.py      TypedDict state
    events.py     Event emitter utilities
    nodes/        One file per graph node
    infra/        External system wrappers (boto3, langchain, lxml)
    prompts/      Markdown prompts
    tests/        Pytest suite with fixtures
dev.sh            Local dev launcher (agentcore dev)
```

## Commands

```bash
# Local dev (container hot-reload)
./dev.sh

# Deploy
AWS_PROFILE=developer-dongik agentcore launch

# Tests
cd app/TriBalanceAgent && uv run pytest -q
```
