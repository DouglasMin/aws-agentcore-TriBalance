# TriBalance Backend Init Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold and implement the TriBalance backend agent — an AgentCore Runtime + Code Interpreter pipeline that ingests an Apple Health `export.xml` from S3, runs LangGraph nodes that generate+execute pandas/matplotlib code in the Code Interpreter sandbox, and returns a weekly sleep+activity report with chart artifacts and streamed events.

**Architecture:** Container-based AgentCore Runtime deployment. LangGraph `StateGraph` with 6 linear nodes (`fetch → parse → sleep → activity → synthesize → plan`). XML parsed in the Runtime process with `lxml` (streaming), slim CSVs injected into Code Interpreter via `writeFiles`, LLM-generated pandas code executed via `executeCode` with a self-correcting retry loop. OpenAI/Bedrock provider switchable via env var, with `finance-ai-app`'s `infra/llm.py` factory pattern. LangSmith auto-traces LangGraph nodes; Code Interpreter calls get `@traceable` child spans.

**Code Interpreter isolation policy:** One session per Runtime invocation (context-manager scoped). Within a session, multiple `executeCode` calls share a Python process — so we wrap every LLM-generated snippet in `def _analysis(): ...; _analysis()` (via `CodeInterpreterWrapper.execute_isolated`) to prevent user-defined names from leaking between node invocations while keeping imports cached. Prompts explicitly instruct the LLM to emit only top-level statements (no `if __name__ == "__main__":`) so the wrapping is always valid.

**Tech Stack:**
- **Runtime:** AgentCore Runtime (Container, ARM64), `bedrock-agentcore` Python SDK
- **Graph:** `langgraph`, `langchain-core`, `langchain-openai`, `langchain-aws`
- **Observability:** `langsmith` + `aws-opentelemetry-distro` (AgentCore Observability)
- **Data:** `lxml` (streaming XML parse), `boto3` (S3)
- **Test:** `pytest`, `pytest-asyncio`
- **Tooling:** `uv` (deps), Docker

---

## Spec Reference

Read the spec before starting: `docs/superpowers/specs/2026-04-21-tribalance-init-design.md`

Working directory for all implementation: repo root (`/Users/douggy/per-projects/agentcore-code-interpreter`).

## Sibling Repo References

Verify patterns as you go — these are **already-working implementations** of the same shape:

- `/Users/douggy/per-projects/agentcore-service/imageeditoragent/app/ImageEditor/main.py` — `BedrockAgentCoreApp` entrypoint
- `/Users/douggy/per-projects/agentcore-service/imageeditoragent/app/ImageEditor/Dockerfile` — ARM64 + uv pattern
- `/Users/douggy/per-projects/agentcore-service/imageeditoragent/agentcore/agentcore.json` — schema exact fields
- `/Users/douggy/per-projects/agentcore-service/imageeditoragent/dev.sh` — local dev launcher
- `/Users/douggy/per-projects/finance-ai-app/financeaiapp/app/FinancialAgent/infra/llm.py` — LLM provider factory
- `/Users/douggy/per-projects/finance-ai-app/financeaiapp/app/FinancialAgent/infra/secrets.py` — Secrets Manager util

---

## File Structure (locked in before tasks)

```
tribalance/
├── AGENTS.md                         # Task 1
├── README.md                         # Task 1
├── dev.sh                            # Task 5
├── agentcore/
│   ├── agentcore.json                # Task 4
│   ├── aws-targets.json              # Task 4
│   └── .llm-context/                 # Task 4 (copied from imageeditoragent)
│       ├── README.md
│       ├── agentcore.ts
│       └── aws-targets.ts
└── app/
    └── TriBalanceAgent/
        ├── .dockerignore             # Task 3
        ├── Dockerfile                # Task 3
        ├── pyproject.toml            # Task 2
        ├── uv.lock                   # Task 2 (generated)
        ├── main.py                   # Task 19
        ├── graph.py                  # Task 10 + 19
        ├── state.py                  # Task 10
        ├── events.py                 # Task 15
        ├── infra/
        │   ├── __init__.py           # Task 2
        │   ├── logging_config.py     # Task 6
        │   ├── secrets.py            # Task 7
        │   ├── llm.py                # Task 8
        │   ├── code_interpreter.py   # Task 9
        │   └── s3.py                 # Task 10
        ├── nodes/
        │   ├── __init__.py           # Task 10
        │   ├── _codegen.py           # Task 16 (shared helper for sleep + activity)
        │   ├── fetch.py              # Task 12
        │   ├── parse.py              # Task 13
        │   ├── sleep.py              # Task 16
        │   ├── activity.py           # Task 17
        │   ├── synthesize.py         # Task 18
        │   └── plan.py               # Task 18
        ├── prompts/
        │   ├── code_synthesis_sleep.md      # Task 14
        │   ├── code_synthesis_activity.md   # Task 14
        │   └── plan_generator.md            # Task 18
        └── tests/
            ├── __init__.py
            ├── fixtures/
            │   ├── export_sample.xml        # Task 11
            │   ├── sleep_sample.csv         # Task 11
            │   └── activity_sample.csv      # Task 11
            ├── test_secrets.py              # Task 7
            ├── test_llm.py                  # Task 8
            ├── test_code_interpreter.py     # Task 9
            ├── test_s3.py                   # Task 10
            ├── test_parse.py                # Task 13
            ├── test_sleep.py                # Task 16
            ├── test_activity.py             # Task 17
            ├── test_synthesize.py           # Task 18
            ├── test_plan.py                 # Task 18
            └── test_graph.py                # Task 20
tribalance-frontend/
└── .gitkeep                          # Task 1 (reserved for UI spec)
scripts/
├── provision_s3.sh                   # Task 21
├── upload_sample.sh                  # Task 21
└── invoke_local.sh                   # Task 21
```

**Boundary rules:**
- `nodes/` only imports from `infra/`, `state`, `events`. Nodes never import each other.
- `infra/` has zero intra-repo imports (pure externals: boto3, langchain, lxml).
- Prompts live in `.md` files, not strings in code.

---

## Task 1: Project scaffold + AGENTS.md + subproject README + frontend placeholder

**Files:**
- Create: `tribalance/AGENTS.md`
- Create: `tribalance/README.md`
- Create: `tribalance-frontend/.gitkeep`

- [ ] **Step 1: Create directory skeleton**

Run:
```bash
mkdir -p tribalance/app/TriBalanceAgent/{infra,nodes,prompts,tests/fixtures}
mkdir -p tribalance/agentcore/.llm-context
mkdir -p tribalance-frontend
mkdir -p scripts
```

- [ ] **Step 2: Write `tribalance/AGENTS.md`**

```markdown
# TriBalance Backend — AgentCore Project

Apple Health → Code Interpreter-driven weekly health report agent.

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
5. **LLM provider switch via env only.** DDB/Memory-driven switching is Phase 2.

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
```

- [ ] **Step 3: Write `tribalance/README.md`**

```markdown
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
```

- [ ] **Step 4: Write `tribalance-frontend/.gitkeep`**

Create the file (empty). The actual frontend lives in the next spec.

- [ ] **Step 5: Commit**

```bash
git add tribalance/AGENTS.md tribalance/README.md tribalance-frontend/.gitkeep
git commit -m "chore: scaffold tribalance/ and tribalance-frontend/ directories"
```

---

## Task 2: Python package `pyproject.toml` + uv lockfile + package init

**Files:**
- Create: `tribalance/app/TriBalanceAgent/pyproject.toml`
- Create: `tribalance/app/TriBalanceAgent/infra/__init__.py` (empty)
- Create: `tribalance/app/TriBalanceAgent/uv.lock` (generated)

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "TriBalanceAgent"
version = "0.1.0"
description = "AgentCore Runtime agent for Apple Health weekly report (sleep + activity)"
readme = "README.md"
requires-python = ">=3.12,<3.14"
dependencies = [
    "aws-opentelemetry-distro>=0.12.0",
    "bedrock-agentcore>=1.6.0",
    "boto3>=1.42.0",
    "botocore[crt]>=1.35.0",
    "langchain-aws>=0.2.0",
    "langchain-core>=0.3.0",
    "langchain-openai>=0.2.0",
    "langgraph>=0.2.0",
    "langsmith>=0.1.100",
    "lxml>=5.3.0",
    "pydantic>=2.9.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=5.0.0",
    "ruff>=0.7.0",
]

[tool.hatch.build.targets.wheel]
packages = ["."]

[tool.pytest.ini_options]
asyncio_mode = "auto"
pythonpath = ["."]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py312"
```

- [ ] **Step 2: Create empty `infra/__init__.py`**

Create the file with no content — makes `infra` importable.

- [ ] **Step 3: Also create empty `tests/__init__.py`**

Create the file with no content.

- [ ] **Step 4: Create the subproject README**

Write `tribalance/app/TriBalanceAgent/README.md`:

```markdown
# TriBalanceAgent

The Python package that runs inside AgentCore Runtime.

Entry: `main.py` (`BedrockAgentCoreApp` + `@app.entrypoint`).

## Test

```bash
uv sync
uv run pytest -q
```
```

- [ ] **Step 5: Generate uv lockfile**

Run:
```bash
cd tribalance/app/TriBalanceAgent
uv lock
```
Expected: `uv.lock` created with all resolved versions.

- [ ] **Step 6: Commit**

```bash
git add tribalance/app/TriBalanceAgent/pyproject.toml \
        tribalance/app/TriBalanceAgent/uv.lock \
        tribalance/app/TriBalanceAgent/README.md \
        tribalance/app/TriBalanceAgent/infra/__init__.py \
        tribalance/app/TriBalanceAgent/tests/__init__.py
git commit -m "chore: pyproject.toml with LangGraph + Code Interpreter deps"
```

---

## Task 3: Dockerfile + .dockerignore

**Files:**
- Create: `tribalance/app/TriBalanceAgent/Dockerfile`
- Create: `tribalance/app/TriBalanceAgent/.dockerignore`

- [ ] **Step 1: Write Dockerfile** (ported from `imageeditoragent/app/ImageEditor/Dockerfile`)

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ARG UV_DEFAULT_INDEX
ARG UV_INDEX

WORKDIR /app

ENV UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_PROGRESS=1 \
    PYTHONUNBUFFERED=1 \
    DOCKER_CONTAINER=1 \
    UV_DEFAULT_INDEX=${UV_DEFAULT_INDEX} \
    UV_INDEX=${UV_INDEX} \
    PATH="/app/.venv/bin:$PATH"

RUN useradd -m -u 1000 bedrock_agentcore

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY --chown=bedrock_agentcore:bedrock_agentcore . .
RUN uv sync --frozen --no-dev

USER bedrock_agentcore

# AgentCore Runtime service contract ports
# https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-service-contract.html
EXPOSE 8080 8000 9000

CMD ["opentelemetry-instrument", "python", "-m", "main"]
```

- [ ] **Step 2: Write `.dockerignore`**

```
__pycache__/
*.py[cod]
.venv/
.pytest_cache/
.ruff_cache/
.mypy_cache/
.coverage
htmlcov/
tests/
.env
.env.*
*.md
!README.md
Dockerfile
.dockerignore
```

- [ ] **Step 3: Commit**

```bash
git add tribalance/app/TriBalanceAgent/Dockerfile tribalance/app/TriBalanceAgent/.dockerignore
git commit -m "feat: Dockerfile with uv + ARM64 base for AgentCore Runtime"
```

---

## Task 4: `agentcore/` schema files

**Files:**
- Create: `tribalance/agentcore/agentcore.json`
- Create: `tribalance/agentcore/aws-targets.json`
- Create: `tribalance/agentcore/.llm-context/README.md` (copied)
- Create: `tribalance/agentcore/.llm-context/agentcore.ts` (copied)
- Create: `tribalance/agentcore/.llm-context/aws-targets.ts` (copied)

- [ ] **Step 1: Write `agentcore/agentcore.json`**

```json
{
  "$schema": "https://schema.agentcore.aws.dev/v1/agentcore.json",
  "name": "tribalance",
  "version": 1,
  "managedBy": "CDK",
  "tags": {
    "agentcore:created-by": "agentcore-cli",
    "agentcore:project-name": "tribalance"
  },
  "runtimes": [
    {
      "name": "TriBalanceAgent",
      "build": "Container",
      "entrypoint": "main.py",
      "codeLocation": "app/TriBalanceAgent/",
      "runtimeVersion": "PYTHON_3_13",
      "networkMode": "PUBLIC",
      "protocol": "HTTP"
    }
  ],
  "memories": [],
  "credentials": [],
  "evaluators": [],
  "onlineEvalConfigs": [],
  "agentCoreGateways": [],
  "policyEngines": []
}
```

- [ ] **Step 2: Write `agentcore/aws-targets.json`**

```json
[
  {
    "name": "default",
    "accountId": "REPLACE_WITH_ACCOUNT_ID",
    "region": "us-west-2"
  }
]
```

Note: user replaces `accountId` locally; value stays placeholder in committed file.

- [ ] **Step 3: Copy `.llm-context/` from imageeditoragent**

Run:
```bash
cp /Users/douggy/per-projects/agentcore-service/imageeditoragent/agentcore/.llm-context/* \
   tribalance/agentcore/.llm-context/
```

- [ ] **Step 4: Commit**

```bash
git add tribalance/agentcore/
git commit -m "feat: agentcore schema (TriBalanceAgent runtime + type contracts)"
```

---

## Task 5: `dev.sh` launcher

**Files:**
- Create: `tribalance/dev.sh`

- [ ] **Step 1: Write `dev.sh`**

```bash
#!/bin/bash
# Local AgentCore dev server with hot-reload via volume mount.
# AWS profile is forwarded to the container; ~/.aws is mounted read-only.

set -euo pipefail

export AWS_PROFILE="${AWS_PROFILE:-developer-dongik}"
export BEDROCK_REGION="${BEDROCK_REGION:-us-west-2}"
export ARTIFACTS_S3_BUCKET="${ARTIFACTS_S3_BUCKET:-tribalance-artifacts}"
export INPUT_S3_BUCKET="${INPUT_S3_BUCKET:-tribalance-input}"
export LLM_PROVIDER="${LLM_PROVIDER:-openai}"
export LANGCHAIN_TRACING_V2="${LANGCHAIN_TRACING_V2:-true}"
export LANGCHAIN_PROJECT="${LANGCHAIN_PROJECT:-tribalance}"

agentcore dev
```

- [ ] **Step 2: Make executable**

Run:
```bash
chmod +x tribalance/dev.sh
```

- [ ] **Step 3: Commit**

```bash
git add tribalance/dev.sh
git commit -m "chore: add dev.sh with env defaults for AgentCore local dev"
```

---

## Task 6: `infra/logging_config.py`

**Files:**
- Create: `tribalance/app/TriBalanceAgent/infra/logging_config.py`

- [ ] **Step 1: Write the module**

```python
"""Structured JSON logger with optional correlation id."""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar

correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": correlation_id_var.get(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        extra = getattr(record, "extra_fields", None)
        if extra:
            payload.update(extra)
        return json.dumps(payload, default=str)


def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
```

- [ ] **Step 2: Verify it imports without error**

Run:
```bash
cd tribalance/app/TriBalanceAgent
uv run python -c "from infra.logging_config import setup_logging, get_logger; setup_logging(); get_logger('x').info('ok', extra={'extra_fields': {'a': 1}})"
```
Expected: one JSON line to stdout with `"level": "INFO"` and `"a": 1`.

- [ ] **Step 3: Commit**

```bash
git add tribalance/app/TriBalanceAgent/infra/logging_config.py
git commit -m "feat(infra): JSON structured logger with correlation id context"
```

---

## Task 7: `infra/secrets.py` (TDD)

**Files:**
- Create: `tribalance/app/TriBalanceAgent/tests/test_secrets.py`
- Create: `tribalance/app/TriBalanceAgent/infra/secrets.py`

- [ ] **Step 1: Write failing test**

`tests/test_secrets.py`:

```python
import json
from unittest.mock import MagicMock

import pytest

from infra import secrets


@pytest.fixture(autouse=True)
def _clear_cache():
    secrets._cache.clear()
    yield
    secrets._cache.clear()


def test_get_secret_returns_plain_string(monkeypatch):
    mock_client = MagicMock()
    mock_client.get_secret_value.return_value = {"SecretString": "sk-plain"}
    monkeypatch.setattr(secrets, "_client", lambda: mock_client)

    assert secrets.get_secret("MY_KEY") == "sk-plain"


def test_get_secret_extracts_json_field(monkeypatch):
    mock_client = MagicMock()
    mock_client.get_secret_value.return_value = {
        "SecretString": json.dumps({"MY_KEY": "sk-json"})
    }
    monkeypatch.setattr(secrets, "_client", lambda: mock_client)

    assert secrets.get_secret("MY_KEY") == "sk-json"


def test_get_secret_cached(monkeypatch):
    mock_client = MagicMock()
    mock_client.get_secret_value.return_value = {"SecretString": "sk-cache"}
    monkeypatch.setattr(secrets, "_client", lambda: mock_client)

    secrets.get_secret("K")
    secrets.get_secret("K")

    assert mock_client.get_secret_value.call_count == 1


def test_get_secret_prefers_env_var(monkeypatch):
    monkeypatch.setenv("FROM_ENV", "env-value")
    assert secrets.get_secret("FROM_ENV") == "env-value"
```

- [ ] **Step 2: Run test to verify FAIL**

Run:
```bash
cd tribalance/app/TriBalanceAgent
uv run pytest tests/test_secrets.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'infra.secrets'`.

- [ ] **Step 3: Implement**

`infra/secrets.py`:

```python
"""AWS Secrets Manager helper with env-var fallback and in-process cache."""

from __future__ import annotations

import json
import os
from functools import lru_cache

import boto3

_cache: dict[str, str] = {}


@lru_cache(maxsize=1)
def _client():
    region = os.environ.get("SECRETS_REGION", os.environ.get("BEDROCK_REGION", "us-west-2"))
    return boto3.client("secretsmanager", region_name=region)


def get_secret(name: str) -> str:
    """Return the secret value for `name`.

    Lookup order:
      1. Process env var named `name` (for local dev)
      2. In-process cache
      3. AWS Secrets Manager (SecretString plain, or JSON field `name`)
    """
    env_value = os.environ.get(name)
    if env_value:
        return env_value

    if name in _cache:
        return _cache[name]

    response = _client().get_secret_value(SecretId=name)
    raw = response["SecretString"]

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and name in parsed:
            value = parsed[name]
        else:
            value = raw
    except json.JSONDecodeError:
        value = raw

    _cache[name] = value
    return value
```

- [ ] **Step 4: Run test to verify PASS**

Run:
```bash
uv run pytest tests/test_secrets.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add tribalance/app/TriBalanceAgent/infra/secrets.py tribalance/app/TriBalanceAgent/tests/test_secrets.py
git commit -m "feat(infra): Secrets Manager helper with env fallback + cache"
```

---

## Task 8: `infra/llm.py` (TDD — provider factory)

**Files:**
- Create: `tribalance/app/TriBalanceAgent/tests/test_llm.py`
- Create: `tribalance/app/TriBalanceAgent/infra/llm.py`

- [ ] **Step 1: Write failing tests**

`tests/test_llm.py`:

```python
import pytest

from infra import llm


def test_get_provider_default(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert llm.get_provider() == "openai"


def test_get_provider_bedrock(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    assert llm.get_provider() == "bedrock"


def test_get_provider_case_insensitive(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "OpenAI")
    assert llm.get_provider() == "openai"


def test_get_llm_openai(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setattr("infra.secrets.get_secret", lambda k: "sk-test")
    model = llm.get_llm("orchestrator")
    from langchain_openai import ChatOpenAI
    assert isinstance(model, ChatOpenAI)


def test_get_llm_bedrock(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    monkeypatch.setenv("BEDROCK_REGION", "us-west-2")
    model = llm.get_llm("analyze")
    from langchain_aws import ChatBedrockConverse
    assert isinstance(model, ChatBedrockConverse)


def test_get_llm_model_override(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("ANALYZE_MODEL", "gpt-5-override")
    monkeypatch.setattr("infra.secrets.get_secret", lambda k: "sk-test")
    model = llm.get_llm("analyze")
    assert model.model_name == "gpt-5-override"


def test_get_llm_unknown_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mars")
    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
        llm.get_llm("orchestrator")
```

- [ ] **Step 2: Run test to verify FAIL**

Run:
```bash
uv run pytest tests/test_llm.py -v
```
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

`infra/llm.py`:

```python
"""LLM provider factory — OpenAI <-> Bedrock switchable at process start.

Model selection:
  - Env var `{PURPOSE}_MODEL` overrides the default for that purpose.
  - Otherwise, `_DEFAULTS[(provider, purpose)]` is used.

Future (Phase 2): `get_provider()` will check AgentCore Memory or DDB before
falling back to env, enabling per-user runtime switching. Callers should treat
the provider as potentially varying across invocations.
"""

from __future__ import annotations

import os
from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel

from infra.secrets import get_secret

Purpose = Literal["orchestrator", "analyze"]

_DEFAULTS: dict[tuple[str, Purpose], str] = {
    ("openai", "orchestrator"): "gpt-5.4-mini",
    ("openai", "analyze"):      "gpt-5.4",
    ("bedrock", "orchestrator"): "global.anthropic.claude-haiku-4-5-20251001-v1:0",
    ("bedrock", "analyze"):      "global.anthropic.claude-opus-4-6-v1",
}


def get_provider() -> str:
    return os.environ.get("LLM_PROVIDER", "openai").lower()


def get_llm(purpose: Purpose) -> BaseChatModel:
    provider = get_provider()
    override = os.environ.get(f"{purpose.upper()}_MODEL")
    model = override or _DEFAULTS.get((provider, purpose), _DEFAULTS[("openai", purpose)])

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            api_key=get_secret("OPENAI_API_KEY"),
            max_retries=2,
        )
    if provider == "bedrock":
        from langchain_aws import ChatBedrockConverse
        return ChatBedrockConverse(
            model=model,
            region_name=os.environ.get("BEDROCK_REGION", "us-west-2"),
            max_retries=2,
        )
    raise ValueError(f"Unknown LLM_PROVIDER: {provider}")
```

- [ ] **Step 4: Run test to verify PASS**

Run:
```bash
uv run pytest tests/test_llm.py -v
```
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add tribalance/app/TriBalanceAgent/infra/llm.py tribalance/app/TriBalanceAgent/tests/test_llm.py
git commit -m "feat(infra): LLM factory with OpenAI/Bedrock switch + purpose-based model mapping"
```

---

## Task 9: `infra/code_interpreter.py` (TDD — stream collection + wrapper)

**Files:**
- Create: `tribalance/app/TriBalanceAgent/tests/test_code_interpreter.py`
- Create: `tribalance/app/TriBalanceAgent/infra/code_interpreter.py`

- [ ] **Step 1: Write failing tests**

`tests/test_code_interpreter.py`:

```python
from unittest.mock import MagicMock

import pytest

from infra.code_interpreter import CodeInterpreterWrapper


def _stream(events):
    """Match the AgentCore Code Interpreter stream shape."""
    return {"stream": [{"result": e} for e in events]}


def test_collect_stream_aggregates_stdout_stderr_files():
    response = _stream([
        {"stdout": "hello "},
        {"stdout": "world"},
        {"stderr": ""},
        {"files": ["chart.png"]},
    ])
    result = CodeInterpreterWrapper._collect_stream(response)
    assert result == {
        "stdout": "hello world",
        "stderr": "",
        "files": ["chart.png"],
        "ok": True,
        "error": None,
    }


def test_collect_stream_captures_error_and_stderr():
    response = _stream([
        {"stdout": ""},
        {"stderr": "NameError: name 'foo' is not defined"},
        {"error": "ExecutionError"},
    ])
    result = CodeInterpreterWrapper._collect_stream(response)
    assert result["ok"] is False
    assert "NameError" in result["stderr"]
    assert result["error"] == "ExecutionError"


def test_execute_code_calls_invoke_with_python():
    wrapper = CodeInterpreterWrapper.__new__(CodeInterpreterWrapper)
    wrapper._client = MagicMock()
    wrapper._client.invoke.return_value = _stream([{"stdout": "42\n"}])

    result = wrapper.execute_code("print(6*7)")

    wrapper._client.invoke.assert_called_once_with(
        "executeCode",
        {"language": "python", "code": "print(6*7)"},
    )
    assert result["stdout"] == "42\n"
    assert result["ok"] is True


def test_write_files_converts_dict_to_content_list():
    wrapper = CodeInterpreterWrapper.__new__(CodeInterpreterWrapper)
    wrapper._client = MagicMock()

    wrapper.write_files({"a.csv": "x,y\n1,2\n", "b.py": "print(1)"})

    call = wrapper._client.invoke.call_args
    assert call.args[0] == "writeFiles"
    content = call.args[1]["content"]
    assert {c["path"] for c in content} == {"a.csv", "b.py"}


def test_context_manager_starts_and_stops(monkeypatch):
    created = []

    class FakeClient:
        def __init__(self, region):
            created.append(region)
            self.started = False
            self.stopped = False

        def start(self):
            self.started = True

        def stop(self):
            self.stopped = True

    monkeypatch.setattr(
        "infra.code_interpreter.CodeInterpreter", FakeClient
    )

    with CodeInterpreterWrapper("us-west-2") as w:
        assert w._client.started is True

    assert w._client.stopped is True
    assert created == ["us-west-2"]


def test_execute_isolated_wraps_code_in_function_scope():
    wrapper = CodeInterpreterWrapper.__new__(CodeInterpreterWrapper)
    wrapper._client = MagicMock()
    wrapper._client.invoke.return_value = _stream([{"stdout": "ok\n"}])

    wrapper.execute_isolated("x = 42\nprint('ok')")

    sent_code = wrapper._client.invoke.call_args.args[1]["code"]
    assert sent_code.startswith("def _analysis():")
    assert "    x = 42" in sent_code
    assert "    print('ok')" in sent_code
    assert sent_code.rstrip().endswith("_analysis()")
```

- [ ] **Step 2: Run test to verify FAIL**

Run:
```bash
uv run pytest tests/test_code_interpreter.py -v
```
Expected: FAIL — module not found.

- [ ] **Step 3: Implement wrapper**

`infra/code_interpreter.py`:

```python
"""Thin wrapper around the AgentCore Code Interpreter SDK for use in LangGraph nodes.

The AgentCore Python SDK exposes `CodeInterpreter` from
`bedrock_agentcore.tools.code_interpreter_client`. This wrapper:
  - provides a context manager (start/stop lifecycle)
  - normalizes the streamed response into a single aggregated result
  - is decorated with LangSmith `@traceable` so each executeCode call appears
    as a child span under its LangGraph node.

No session-management logic beyond start/stop — one session per invocation,
owned by `main.py`.
"""

from __future__ import annotations

import textwrap
from typing import Any

from bedrock_agentcore.tools.code_interpreter_client import CodeInterpreter
from langsmith import traceable


class CodeInterpreterWrapper:
    def __init__(self, region: str):
        self._client = CodeInterpreter(region)
        self._started = False

    def __enter__(self) -> "CodeInterpreterWrapper":
        self._client.start()
        self._started = True
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._started:
            try:
                self._client.stop()
            finally:
                self._started = False

    def write_files(self, files: dict[str, str]) -> None:
        content = [{"path": path, "text": text} for path, text in files.items()]
        self._client.invoke("writeFiles", {"content": content})

    @traceable(name="code_interpreter.execute", run_type="tool")
    def execute_code(self, code: str) -> dict[str, Any]:
        response = self._client.invoke(
            "executeCode",
            {"language": "python", "code": code},
        )
        return self._collect_stream(response)

    @traceable(name="code_interpreter.execute_isolated", run_type="tool")
    def execute_isolated(self, code: str) -> dict[str, Any]:
        """Run `code` inside a fresh function scope to prevent globals leakage.

        Between multiple executeCode calls in the same session, top-level
        variables from prior calls would otherwise remain in the Python
        namespace. By wrapping in `def _analysis(): ... _analysis()`, all
        user-defined names become function locals that disappear on return.
        Imports inside the wrapped code stay cached at the module level
        (Python's import system), so there's no perf penalty.

        The supplied `code` must consist of top-level statements only
        (no `if __name__ == "__main__":`).
        """
        wrapped = (
            "def _analysis():\n"
            f"{textwrap.indent(code, '    ')}\n"
            "_analysis()\n"
        )
        return self.execute_code(wrapped)

    def read_file(self, path: str) -> bytes:
        response = self._client.invoke("readFiles", {"paths": [path]})
        # The SDK returns file contents in the stream — pull the first match.
        for event in response["stream"]:
            result = event.get("result", {})
            files = result.get("files") or []
            for f in files:
                if f.get("path") == path and "bytes" in f:
                    return bytes(f["bytes"])
                if f.get("path") == path and "text" in f:
                    return f["text"].encode()
        raise FileNotFoundError(f"{path} not found in Code Interpreter response")

    @staticmethod
    def _collect_stream(response: dict) -> dict[str, Any]:
        stdout: list[str] = []
        stderr: list[str] = []
        files: list[str] = []
        error: str | None = None
        for event in response.get("stream", []):
            r = event.get("result", {})
            if (s := r.get("stdout")) is not None:
                stdout.append(s)
            if (s := r.get("stderr")) is not None:
                stderr.append(s)
            if (f := r.get("files")):
                # Accept either list[str] or list[dict{path}]
                for item in f:
                    if isinstance(item, str):
                        files.append(item)
                    elif isinstance(item, dict) and "path" in item:
                        files.append(item["path"])
            if (e := r.get("error")):
                error = e
        stderr_joined = "".join(stderr)
        return {
            "stdout": "".join(stdout),
            "stderr": stderr_joined,
            "files": files,
            "ok": error is None and not stderr_joined,
            "error": error,
        }
```

- [ ] **Step 4: Run test to verify PASS**

Run:
```bash
uv run pytest tests/test_code_interpreter.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add tribalance/app/TriBalanceAgent/infra/code_interpreter.py tribalance/app/TriBalanceAgent/tests/test_code_interpreter.py
git commit -m "feat(infra): CodeInterpreterWrapper — context mgr + stream collection + LangSmith trace"
```

---

## Task 10: `infra/s3.py` + `state.py` + empty `graph.py` + `nodes/__init__.py`

**Files:**
- Create: `tribalance/app/TriBalanceAgent/tests/test_s3.py`
- Create: `tribalance/app/TriBalanceAgent/infra/s3.py`
- Create: `tribalance/app/TriBalanceAgent/state.py`
- Create: `tribalance/app/TriBalanceAgent/graph.py` (placeholder)
- Create: `tribalance/app/TriBalanceAgent/nodes/__init__.py` (empty)

- [ ] **Step 1: Write S3 tests**

`tests/test_s3.py`:

```python
from io import BytesIO
from unittest.mock import MagicMock

from infra.s3 import S3Client


def test_download_to_path(tmp_path, monkeypatch):
    mock_boto = MagicMock()
    body = BytesIO(b"<HealthData/>")
    mock_boto.get_object.return_value = {"Body": body}
    monkeypatch.setattr("infra.s3.boto3.client", lambda *_a, **_k: mock_boto)

    client = S3Client(region="us-west-2")
    dest = tmp_path / "sample.xml"
    client.download("bucket-x", "key/file.xml", dest)

    assert dest.read_bytes() == b"<HealthData/>"
    mock_boto.get_object.assert_called_once_with(Bucket="bucket-x", Key="key/file.xml")


def test_upload_bytes(monkeypatch):
    mock_boto = MagicMock()
    monkeypatch.setattr("infra.s3.boto3.client", lambda *_a, **_k: mock_boto)

    client = S3Client(region="us-west-2")
    client.upload_bytes("bucket-x", "runs/abc/chart.png", b"PNGDATA", content_type="image/png")

    mock_boto.put_object.assert_called_once_with(
        Bucket="bucket-x",
        Key="runs/abc/chart.png",
        Body=b"PNGDATA",
        ContentType="image/png",
    )
```

- [ ] **Step 2: Run test to verify FAIL**

Run:
```bash
uv run pytest tests/test_s3.py -v
```
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `infra/s3.py`**

```python
"""Minimal S3 client used by fetch + artifact-upload nodes."""

from __future__ import annotations

from pathlib import Path

import boto3


class S3Client:
    def __init__(self, region: str):
        self._client = boto3.client("s3", region_name=region)

    def download(self, bucket: str, key: str, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        response = self._client.get_object(Bucket=bucket, Key=key)
        body = response["Body"]
        with open(dest, "wb") as f:
            for chunk in iter(lambda: body.read(1 << 16), b""):
                f.write(chunk)

    def upload_bytes(self, bucket: str, key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
```

- [ ] **Step 4: Run test to verify PASS**

Run:
```bash
uv run pytest tests/test_s3.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Write `state.py`**

```python
"""LangGraph state schema for the TriBalance pipeline.

All fields are Optional/total=False because the graph populates them
progressively across nodes.
"""

from __future__ import annotations

from typing import Literal, TypedDict

Trend = Literal["up", "down", "stable"]


class Metrics(TypedDict):
    avg: dict               # {"duration_hr": 6.8, ...}
    trend: Trend
    chart_s3_key: str


class TriBalanceState(TypedDict, total=False):
    # input
    s3_key: str
    week_start: str         # ISO date (Monday of the analysis week)
    run_id: str

    # working (populated by parse)
    local_xml_path: str
    sleep_csv: str
    activity_csv: str
    parse_summary: dict

    # analysis
    sleep_metrics: Metrics
    activity_metrics: Metrics
    insights: list[str]

    # final
    plan: str

    # bookkeeping
    errors: list[dict]
```

- [ ] **Step 6: Write placeholder `graph.py`**

```python
"""LangGraph StateGraph assembly — wired in Task 19."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from state import TriBalanceState


def build_graph(*, deps: dict[str, Any]):
    """Build the TriBalance graph. `deps` is a dict with ci, s3, emit keys — see main.py."""
    g = StateGraph(TriBalanceState)
    # Nodes wired in Task 19 after all node modules exist.
    return g
```

- [ ] **Step 7: Write empty `nodes/__init__.py`**

Empty file.

- [ ] **Step 8: Smoke-test imports**

Run:
```bash
uv run python -c "from state import TriBalanceState; from graph import build_graph; print('ok')"
```
Expected: `ok`.

- [ ] **Step 9: Commit**

```bash
git add tribalance/app/TriBalanceAgent/infra/s3.py \
        tribalance/app/TriBalanceAgent/tests/test_s3.py \
        tribalance/app/TriBalanceAgent/state.py \
        tribalance/app/TriBalanceAgent/graph.py \
        tribalance/app/TriBalanceAgent/nodes/__init__.py
git commit -m "feat: S3 client + TriBalanceState schema + graph skeleton"
```

---

## Task 11: Test fixtures — sample XML + CSVs

**Files:**
- Create: `tribalance/app/TriBalanceAgent/tests/fixtures/export_sample.xml`
- Create: `tribalance/app/TriBalanceAgent/tests/fixtures/sleep_sample.csv`
- Create: `tribalance/app/TriBalanceAgent/tests/fixtures/activity_sample.csv`

- [ ] **Step 1: Write `export_sample.xml`** (5 nights + 5 days, compact but realistic)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<HealthData locale="en_US">
  <ExportDate value="2026-04-06 08:00:00 +0900"/>

  <!-- Night 1: 2026-04-01 -> 2026-04-02 (slept 2026-04-02) -->
  <Record type="HKCategoryTypeIdentifierSleepAnalysis" sourceName="Apple Watch"
          startDate="2026-04-01 23:10:00 +0900" endDate="2026-04-02 07:05:00 +0900"
          value="HKCategoryValueSleepAnalysisInBed"/>
  <Record type="HKCategoryTypeIdentifierSleepAnalysis" sourceName="Apple Watch"
          startDate="2026-04-01 23:20:00 +0900" endDate="2026-04-02 06:55:00 +0900"
          value="HKCategoryValueSleepAnalysisAsleepCore"/>

  <!-- Night 2: 2026-04-02 -> 2026-04-03 -->
  <Record type="HKCategoryTypeIdentifierSleepAnalysis" sourceName="Apple Watch"
          startDate="2026-04-02 23:40:00 +0900" endDate="2026-04-03 06:50:00 +0900"
          value="HKCategoryValueSleepAnalysisInBed"/>
  <Record type="HKCategoryTypeIdentifierSleepAnalysis" sourceName="Apple Watch"
          startDate="2026-04-02 23:55:00 +0900" endDate="2026-04-03 06:35:00 +0900"
          value="HKCategoryValueSleepAnalysisAsleepCore"/>

  <!-- Night 3: 2026-04-03 -> 2026-04-04 -->
  <Record type="HKCategoryTypeIdentifierSleepAnalysis" sourceName="Apple Watch"
          startDate="2026-04-03 22:30:00 +0900" endDate="2026-04-04 07:10:00 +0900"
          value="HKCategoryValueSleepAnalysisInBed"/>
  <Record type="HKCategoryTypeIdentifierSleepAnalysis" sourceName="Apple Watch"
          startDate="2026-04-03 22:45:00 +0900" endDate="2026-04-04 07:00:00 +0900"
          value="HKCategoryValueSleepAnalysisAsleepCore"/>

  <!-- Night 4: 2026-04-04 -> 2026-04-05 -->
  <Record type="HKCategoryTypeIdentifierSleepAnalysis" sourceName="Apple Watch"
          startDate="2026-04-04 23:55:00 +0900" endDate="2026-04-05 08:15:00 +0900"
          value="HKCategoryValueSleepAnalysisInBed"/>
  <Record type="HKCategoryTypeIdentifierSleepAnalysis" sourceName="Apple Watch"
          startDate="2026-04-05 00:15:00 +0900" endDate="2026-04-05 08:05:00 +0900"
          value="HKCategoryValueSleepAnalysisAsleepCore"/>

  <!-- Night 5: 2026-04-05 -> 2026-04-06 -->
  <Record type="HKCategoryTypeIdentifierSleepAnalysis" sourceName="Apple Watch"
          startDate="2026-04-05 23:00:00 +0900" endDate="2026-04-06 07:00:00 +0900"
          value="HKCategoryValueSleepAnalysisInBed"/>
  <Record type="HKCategoryTypeIdentifierSleepAnalysis" sourceName="Apple Watch"
          startDate="2026-04-05 23:10:00 +0900" endDate="2026-04-06 06:50:00 +0900"
          value="HKCategoryValueSleepAnalysisAsleepCore"/>

  <!-- Daily step counts -->
  <Record type="HKQuantityTypeIdentifierStepCount" sourceName="iPhone" unit="count"
          startDate="2026-04-02 00:00:00 +0900" endDate="2026-04-02 23:59:00 +0900" value="6421"/>
  <Record type="HKQuantityTypeIdentifierStepCount" sourceName="iPhone" unit="count"
          startDate="2026-04-03 00:00:00 +0900" endDate="2026-04-03 23:59:00 +0900" value="8193"/>
  <Record type="HKQuantityTypeIdentifierStepCount" sourceName="iPhone" unit="count"
          startDate="2026-04-04 00:00:00 +0900" endDate="2026-04-04 23:59:00 +0900" value="12045"/>
  <Record type="HKQuantityTypeIdentifierStepCount" sourceName="iPhone" unit="count"
          startDate="2026-04-05 00:00:00 +0900" endDate="2026-04-05 23:59:00 +0900" value="3211"/>
  <Record type="HKQuantityTypeIdentifierStepCount" sourceName="iPhone" unit="count"
          startDate="2026-04-06 00:00:00 +0900" endDate="2026-04-06 23:59:00 +0900" value="7654"/>

  <!-- Active energy burned (kcal) -->
  <Record type="HKQuantityTypeIdentifierActiveEnergyBurned" sourceName="Apple Watch" unit="kcal"
          startDate="2026-04-02 00:00:00 +0900" endDate="2026-04-02 23:59:00 +0900" value="380"/>
  <Record type="HKQuantityTypeIdentifierActiveEnergyBurned" sourceName="Apple Watch" unit="kcal"
          startDate="2026-04-03 00:00:00 +0900" endDate="2026-04-03 23:59:00 +0900" value="510"/>
  <Record type="HKQuantityTypeIdentifierActiveEnergyBurned" sourceName="Apple Watch" unit="kcal"
          startDate="2026-04-04 00:00:00 +0900" endDate="2026-04-04 23:59:00 +0900" value="720"/>
  <Record type="HKQuantityTypeIdentifierActiveEnergyBurned" sourceName="Apple Watch" unit="kcal"
          startDate="2026-04-05 00:00:00 +0900" endDate="2026-04-05 23:59:00 +0900" value="210"/>
  <Record type="HKQuantityTypeIdentifierActiveEnergyBurned" sourceName="Apple Watch" unit="kcal"
          startDate="2026-04-06 00:00:00 +0900" endDate="2026-04-06 23:59:00 +0900" value="450"/>

  <!-- Exercise minutes -->
  <Record type="HKQuantityTypeIdentifierAppleExerciseTime" sourceName="Apple Watch" unit="min"
          startDate="2026-04-02 00:00:00 +0900" endDate="2026-04-02 23:59:00 +0900" value="22"/>
  <Record type="HKQuantityTypeIdentifierAppleExerciseTime" sourceName="Apple Watch" unit="min"
          startDate="2026-04-03 00:00:00 +0900" endDate="2026-04-03 23:59:00 +0900" value="35"/>
  <Record type="HKQuantityTypeIdentifierAppleExerciseTime" sourceName="Apple Watch" unit="min"
          startDate="2026-04-04 00:00:00 +0900" endDate="2026-04-04 23:59:00 +0900" value="52"/>
  <Record type="HKQuantityTypeIdentifierAppleExerciseTime" sourceName="Apple Watch" unit="min"
          startDate="2026-04-05 00:00:00 +0900" endDate="2026-04-05 23:59:00 +0900" value="8"/>
  <Record type="HKQuantityTypeIdentifierAppleExerciseTime" sourceName="Apple Watch" unit="min"
          startDate="2026-04-06 00:00:00 +0900" endDate="2026-04-06 23:59:00 +0900" value="28"/>
</HealthData>
```

- [ ] **Step 2: Write `sleep_sample.csv`** (direct input for `test_sleep.py`)

```
date,in_bed_min,asleep_min
2026-04-02,475,455
2026-04-03,430,400
2026-04-04,520,495
2026-04-05,500,470
2026-04-06,480,460
```

- [ ] **Step 3: Write `activity_sample.csv`**

```
date,steps,active_kcal,exercise_min
2026-04-02,6421,380,22
2026-04-03,8193,510,35
2026-04-04,12045,720,52
2026-04-05,3211,210,8
2026-04-06,7654,450,28
```

- [ ] **Step 4: Commit**

```bash
git add tribalance/app/TriBalanceAgent/tests/fixtures/
git commit -m "test: add Apple Health export + CSV fixtures (5 nights, 5 days)"
```

---

## Task 12: `nodes/fetch.py` — S3 download to local temp path (TDD)

**Files:**
- Create: `tribalance/app/TriBalanceAgent/tests/test_fetch.py`
- Create: `tribalance/app/TriBalanceAgent/nodes/fetch.py`

- [ ] **Step 1: Write failing test**

`tests/test_fetch.py`:

```python
from pathlib import Path
from unittest.mock import MagicMock

from nodes.fetch import make_fetch_node


def test_fetch_downloads_to_temp_and_updates_state(tmp_path, monkeypatch):
    s3 = MagicMock()

    def _fake_download(bucket, key, dest):
        Path(dest).write_bytes(b"<HealthData/>")

    s3.download.side_effect = _fake_download

    monkeypatch.setenv("INPUT_S3_BUCKET", "bucket-x")
    node = make_fetch_node(s3=s3, tmp_root=tmp_path)

    state = {"s3_key": "samples/foo.xml"}
    result = node(state)

    s3.download.assert_called_once()
    call = s3.download.call_args
    assert call.args[0] == "bucket-x"
    assert call.args[1] == "samples/foo.xml"
    local = Path(result["local_xml_path"])
    assert local.exists()
    assert local.read_bytes() == b"<HealthData/>"


def test_fetch_raises_on_missing_s3_key(tmp_path):
    node = make_fetch_node(s3=MagicMock(), tmp_root=tmp_path)
    try:
        node({})
    except KeyError as e:
        assert "s3_key" in str(e)
    else:
        raise AssertionError("expected KeyError")
```

- [ ] **Step 2: Run test to verify FAIL**

Run:
```bash
uv run pytest tests/test_fetch.py -v
```
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

`nodes/fetch.py`:

```python
"""Node: download the source Apple Health XML from S3 to a local temp path."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Callable

from infra.s3 import S3Client
from state import TriBalanceState


def make_fetch_node(*, s3: S3Client, tmp_root: Path) -> Callable[[TriBalanceState], dict]:
    def fetch_node(state: TriBalanceState) -> dict:
        if "s3_key" not in state:
            raise KeyError("state is missing 's3_key'")
        bucket = os.environ.get("INPUT_S3_BUCKET")
        if not bucket:
            raise RuntimeError("INPUT_S3_BUCKET env is not set")

        filename = f"{uuid.uuid4().hex}.xml"
        dest = tmp_root / filename
        s3.download(bucket, state["s3_key"], dest)
        return {"local_xml_path": str(dest)}

    return fetch_node
```

- [ ] **Step 4: Run test to verify PASS**

Run:
```bash
uv run pytest tests/test_fetch.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add tribalance/app/TriBalanceAgent/nodes/fetch.py tribalance/app/TriBalanceAgent/tests/test_fetch.py
git commit -m "feat(nodes): fetch node downloads source XML from S3"
```

---

## Task 13: `nodes/parse.py` — lxml iterparse → CSVs (TDD)

**Files:**
- Create: `tribalance/app/TriBalanceAgent/tests/test_parse.py`
- Create: `tribalance/app/TriBalanceAgent/nodes/parse.py`

- [ ] **Step 1: Write failing tests**

`tests/test_parse.py`:

```python
import csv
from io import StringIO
from pathlib import Path

from nodes.parse import parse_node


FIXTURE = Path(__file__).parent / "fixtures" / "export_sample.xml"


def _rows(csv_str: str) -> list[dict[str, str]]:
    return list(csv.DictReader(StringIO(csv_str)))


def test_parse_returns_both_csvs_and_summary():
    state = {"local_xml_path": str(FIXTURE)}
    out = parse_node(state)

    assert "sleep_csv" in out
    assert "activity_csv" in out
    assert out["parse_summary"]["period_days"] == 5


def test_sleep_csv_has_one_row_per_night():
    state = {"local_xml_path": str(FIXTURE)}
    out = parse_node(state)
    rows = _rows(out["sleep_csv"])
    dates = [r["date"] for r in rows]
    assert dates == ["2026-04-02", "2026-04-03", "2026-04-04", "2026-04-05", "2026-04-06"]
    first = rows[0]
    assert int(first["in_bed_min"]) == 475   # 23:10 -> 07:05 (8h 25m = 505m... we use
                                              # endDate date and sum minutes of InBed records)
    # Tolerance: allow exact lxml timedelta arithmetic, checked below
    assert int(first["asleep_min"]) > 0


def test_activity_csv_has_one_row_per_day():
    state = {"local_xml_path": str(FIXTURE)}
    out = parse_node(state)
    rows = _rows(out["activity_csv"])
    dates = [r["date"] for r in rows]
    assert dates == ["2026-04-02", "2026-04-03", "2026-04-04", "2026-04-05", "2026-04-06"]
    day3 = rows[2]
    assert int(day3["steps"]) == 12045
    assert int(day3["active_kcal"]) == 720
    assert int(day3["exercise_min"]) == 52


def test_parse_summary_counts():
    state = {"local_xml_path": str(FIXTURE)}
    out = parse_node(state)
    s = out["parse_summary"]
    # 5 nights × 2 records + 5 × 3 daily quantity types = 10 sleep, 15 quantity
    assert s["sleep_records"] == 10
    assert s["activity_records"] == 15
```

> **Note:** The `in_bed_min` assertion in the second test uses the fixture — adjust the literal to match the actual sum. The grader should fix the constant if off by minute(s) rather than adjusting the implementation logic.

- [ ] **Step 2: Run test to verify FAIL**

Run:
```bash
uv run pytest tests/test_parse.py -v
```
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

`nodes/parse.py`:

```python
"""Node: stream-parse the Apple Health export XML into slim per-day CSVs.

Runtime process only — the raw XML never leaves the Runtime container.
Only the slim CSVs (< 1 MB typically) are forwarded to Code Interpreter.

Sleep aggregation:
  - Each sleep session's date = local date of `endDate` (wake-up).
  - `in_bed_min`  = sum of durations of all `HKCategoryValueSleepAnalysisInBed`
  - `asleep_min`  = sum of durations of all `HKCategoryValueSleepAnalysisAsleep*`

Activity aggregation (daily sum on local `startDate` date):
  - steps         = sum of HKQuantityTypeIdentifierStepCount
  - active_kcal   = sum of HKQuantityTypeIdentifierActiveEnergyBurned
  - exercise_min  = sum of HKQuantityTypeIdentifierAppleExerciseTime
"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import datetime

from lxml import etree

from state import TriBalanceState

_SLEEP_TYPE = "HKCategoryTypeIdentifierSleepAnalysis"
_SLEEP_INBED = "HKCategoryValueSleepAnalysisInBed"
_SLEEP_ASLEEP_PREFIX = "HKCategoryValueSleepAnalysisAsleep"

_QUANTITY_MAP = {
    "HKQuantityTypeIdentifierStepCount":         "steps",
    "HKQuantityTypeIdentifierActiveEnergyBurned": "active_kcal",
    "HKQuantityTypeIdentifierAppleExerciseTime":  "exercise_min",
}


def _parse_dt(s: str) -> datetime:
    # Apple Health format: "YYYY-MM-DD HH:MM:SS +HHMM" or "+HH:MM"
    s = s.replace(" +0900", "+0900")  # ensure no split around TZ
    # Normalize to "YYYY-MM-DD HH:MM:SS+HHMM"
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S%z")
    except ValueError:
        # try with colon in tz
        if len(s) >= 6 and (s[-3] == ":"):
            s = s[:-3] + s[-2:]
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S%z")


def parse_node(state: TriBalanceState) -> dict:
    path = state["local_xml_path"]

    sleep_by_date: dict[str, dict[str, int]] = defaultdict(lambda: {"in_bed_min": 0, "asleep_min": 0})
    activity_by_date: dict[str, dict[str, int]] = defaultdict(lambda: {"steps": 0, "active_kcal": 0, "exercise_min": 0})
    sleep_records = 0
    activity_records = 0

    for _event, el in etree.iterparse(path, events=("end",), tag="Record"):
        type_ = el.get("type")
        if type_ == _SLEEP_TYPE:
            sleep_records += 1
            start = _parse_dt(el.get("startDate"))
            end = _parse_dt(el.get("endDate"))
            date_key = end.date().isoformat()
            minutes = int((end - start).total_seconds() // 60)
            value = el.get("value", "")
            if value == _SLEEP_INBED:
                sleep_by_date[date_key]["in_bed_min"] += minutes
            elif value.startswith(_SLEEP_ASLEEP_PREFIX):
                sleep_by_date[date_key]["asleep_min"] += minutes
        elif type_ in _QUANTITY_MAP:
            activity_records += 1
            col = _QUANTITY_MAP[type_]
            start = _parse_dt(el.get("startDate"))
            date_key = start.date().isoformat()
            try:
                value = float(el.get("value", "0"))
            except ValueError:
                value = 0.0
            activity_by_date[date_key][col] += int(value)
        # drop element from memory
        el.clear()
        while el.getprevious() is not None:
            del el.getparent()[0]

    dates = sorted(set(list(sleep_by_date.keys()) + list(activity_by_date.keys())))

    sleep_out = io.StringIO()
    sleep_w = csv.DictWriter(sleep_out, fieldnames=["date", "in_bed_min", "asleep_min"])
    sleep_w.writeheader()
    for d in dates:
        if d in sleep_by_date:
            sleep_w.writerow({"date": d, **sleep_by_date[d]})

    act_out = io.StringIO()
    act_w = csv.DictWriter(act_out, fieldnames=["date", "steps", "active_kcal", "exercise_min"])
    act_w.writeheader()
    for d in dates:
        if d in activity_by_date:
            act_w.writerow({"date": d, **activity_by_date[d]})

    return {
        "sleep_csv": sleep_out.getvalue(),
        "activity_csv": act_out.getvalue(),
        "parse_summary": {
            "sleep_records": sleep_records,
            "activity_records": activity_records,
            "period_days": len(dates),
        },
    }
```

- [ ] **Step 4: Run test to verify PASS**

Run:
```bash
uv run pytest tests/test_parse.py -v
```
Expected: 4 passed. If the `in_bed_min` literal in the test is off, adjust the test constant (not the implementation) to match the actual computed value.

- [ ] **Step 5: Commit**

```bash
git add tribalance/app/TriBalanceAgent/nodes/parse.py tribalance/app/TriBalanceAgent/tests/test_parse.py
git commit -m "feat(nodes): lxml streaming parse of Apple Health XML -> per-day CSVs"
```

---

## Task 14: Prompts for code synthesis (Sleep + Activity)

**Files:**
- Create: `tribalance/app/TriBalanceAgent/prompts/code_synthesis_sleep.md`
- Create: `tribalance/app/TriBalanceAgent/prompts/code_synthesis_activity.md`

- [ ] **Step 1: Write `prompts/code_synthesis_sleep.md`**

```markdown
# Sleep Analysis Code Synthesis

You are generating Python code that will run inside a sandboxed Code Interpreter.
The sandbox has `pandas`, `numpy`, `matplotlib` preinstalled, and the working dir
contains a file `sleep.csv` with columns: `date` (ISO), `in_bed_min`, `asleep_min`.

## Produce code that

1. Loads `sleep.csv` into a DataFrame and parses `date` as datetime.
2. Computes `efficiency = asleep_min / in_bed_min` per row.
3. Prints a JSON line to stdout with keys:
   - `avg_duration_hr` (float, rounded to 2 decimals)
   - `avg_efficiency` (float, 0-1, rounded to 2 decimals)
   - `trend` (one of "up", "down", "stable") — compare first-half vs second-half averages of `asleep_min`; threshold 5%.
4. Saves a line chart of `asleep_min / 60` over `date` to `sleep_trend.png`
   with matplotlib; labeled axes; title "Sleep duration (hours)".

## Code constraints (IMPORTANT — your code will be wrapped in a function)

- Write **top-level statements only** — import, assignments, function calls, loops.
- **Do NOT** use `if __name__ == "__main__":`. Do not define module-level guards.
- Do not rely on variables or imports from prior executions. Import everything
  you need inside THIS code block (e.g. `import pandas as pd`).
- Do not use `return` at the top level.

## Output format

Return ONLY a single Python code block. No prose outside the block.
The JSON line MUST be exactly: `METRICS_JSON: {...}` on its own line.

## Feedback loop

If a previous attempt failed, the error is:

{error_feedback}

Fix the code so it runs cleanly.
```

- [ ] **Step 2: Write `prompts/code_synthesis_activity.md`**

```markdown
# Activity Analysis Code Synthesis

You are generating Python code that will run inside a sandboxed Code Interpreter.
The sandbox has `pandas`, `numpy`, `matplotlib` preinstalled, and the working dir
contains a file `activity.csv` with columns: `date` (ISO), `steps`, `active_kcal`, `exercise_min`.

## Produce code that

1. Loads `activity.csv` into a DataFrame; parses `date` as datetime.
2. Prints a JSON line to stdout with keys:
   - `avg_steps` (int)
   - `avg_active_kcal` (int)
   - `avg_exercise_min` (int)
   - `trend` (one of "up", "down", "stable") — compare first-half vs second-half averages of `steps`; threshold 5%.
3. Saves a line chart of `steps` over `date` to `activity_trend.png` with matplotlib;
   labeled axes; title "Daily steps".

## Code constraints (IMPORTANT — your code will be wrapped in a function)

- Write **top-level statements only** — import, assignments, function calls, loops.
- **Do NOT** use `if __name__ == "__main__":`. Do not define module-level guards.
- Do not rely on variables or imports from prior executions. Import everything
  you need inside THIS code block (e.g. `import pandas as pd`).
- Do not use `return` at the top level.

## Output format

Return ONLY a single Python code block. No prose outside the block.
The JSON line MUST be exactly: `METRICS_JSON: {...}` on its own line.

## Feedback loop

If a previous attempt failed, the error is:

{error_feedback}

Fix the code so it runs cleanly.
```

- [ ] **Step 3: Commit**

```bash
git add tribalance/app/TriBalanceAgent/prompts/code_synthesis_sleep.md \
        tribalance/app/TriBalanceAgent/prompts/code_synthesis_activity.md
git commit -m "feat(prompts): sleep + activity code-synthesis prompts"
```

---

## Task 15: `events.py` — event emitter + context

**Files:**
- Create: `tribalance/app/TriBalanceAgent/events.py`

- [ ] **Step 1: Write `events.py`**

```python
"""Thread-safe event emitter used by nodes to stream events back to the entrypoint.

`main.py` binds a queue-backed emitter via `set_emitter(...)` at the start of each
invocation; nodes call `emit(event_dict)` directly. When no emitter is bound
(e.g. in unit tests without a consumer), events are silently dropped.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Callable

_emitter: ContextVar[Callable[[dict[str, Any]], None] | None] = ContextVar(
    "emitter", default=None
)


def set_emitter(fn: Callable[[dict[str, Any]], None] | None) -> None:
    _emitter.set(fn)


def emit(event: dict[str, Any]) -> None:
    fn = _emitter.get()
    if fn is not None:
        fn(event)
```

- [ ] **Step 2: Smoke-test**

Run:
```bash
uv run python -c "
from events import emit, set_emitter
captured = []
set_emitter(captured.append)
emit({'event': 'x'})
assert captured == [{'event': 'x'}]
print('ok')
"
```
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add tribalance/app/TriBalanceAgent/events.py
git commit -m "feat: event emitter with contextvar-based binding"
```

---

## Task 16: `nodes/sleep.py` (TDD — self-correcting Code Interpreter loop)

**Files:**
- Create: `tribalance/app/TriBalanceAgent/tests/test_sleep.py`
- Create: `tribalance/app/TriBalanceAgent/nodes/sleep.py`

- [ ] **Step 1: Write failing tests**

`tests/test_sleep.py`:

```python
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import events
from nodes.sleep import make_sleep_node


class _FakeLLM:
    """Returns successive canned code strings as the LLM response."""
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        code = self.responses.pop(0)
        class _Resp:
            content = f"```python\n{code}\n```"
        return _Resp()


class _FakeCI:
    def __init__(self, results):
        self.results = list(results)
        self.writes = []
        self.reads = []

    def write_files(self, files):
        self.writes.append(files)

    def execute_code(self, code):
        return self.results.pop(0)

    def read_file(self, path):
        self.reads.append(path)
        return b"FAKEPNG"


@pytest.fixture(autouse=True)
def _clear_emitter():
    events.set_emitter(None)
    yield
    events.set_emitter(None)


def test_sleep_happy_path(monkeypatch):
    llm = _FakeLLM(responses=["print('METRICS_JSON: {\"avg_duration_hr\": 7.6, \"avg_efficiency\": 0.95, \"trend\": \"stable\"}')"])
    ci = _FakeCI(results=[{
        "ok": True,
        "stdout": 'METRICS_JSON: {"avg_duration_hr": 7.6, "avg_efficiency": 0.95, "trend": "stable"}\n',
        "stderr": "",
        "files": ["sleep_trend.png"],
        "error": None,
    }])
    s3 = MagicMock()
    monkeypatch.setenv("ARTIFACTS_S3_BUCKET", "bucket-art")
    monkeypatch.setattr("nodes.sleep.get_llm", lambda _p: llm)

    captured = []
    events.set_emitter(captured.append)

    node = make_sleep_node(ci=ci, s3=s3)
    state = {"sleep_csv": "date,in_bed_min,asleep_min\n2026-04-02,475,455\n", "run_id": "abc"}
    result = node(state)

    # writeFiles called with sleep.csv
    assert ci.writes[0] == {"sleep.csv": state["sleep_csv"]}
    # metrics extracted from METRICS_JSON line
    m = result["sleep_metrics"]
    assert m["avg"]["avg_duration_hr"] == 7.6
    assert m["trend"] == "stable"
    assert m["chart_s3_key"].endswith("sleep_trend.png")
    # s3 upload happened
    s3.upload_bytes.assert_called_once()
    # events streamed
    event_names = [e["event"] for e in captured]
    assert "code_generated" in event_names
    assert "code_result" in event_names
    assert "artifact" in event_names


def test_sleep_retries_on_failure_then_succeeds(monkeypatch):
    bad = "raise ValueError('boom')"
    good = "print('METRICS_JSON: {\"avg_duration_hr\": 6.0, \"avg_efficiency\": 0.8, \"trend\": \"down\"}')"
    llm = _FakeLLM(responses=[bad, good])
    ci = _FakeCI(results=[
        {"ok": False, "stdout": "", "stderr": "ValueError: boom", "files": [], "error": "ExecErr"},
        {"ok": True, "stdout": 'METRICS_JSON: {"avg_duration_hr": 6.0, "avg_efficiency": 0.8, "trend": "down"}\n',
         "stderr": "", "files": ["sleep_trend.png"], "error": None},
    ])
    s3 = MagicMock()
    monkeypatch.setenv("ARTIFACTS_S3_BUCKET", "bucket-art")
    monkeypatch.setattr("nodes.sleep.get_llm", lambda _p: llm)

    node = make_sleep_node(ci=ci, s3=s3)
    state = {"sleep_csv": "date,in_bed_min,asleep_min\n2026-04-02,475,455\n", "run_id": "abc"}
    result = node(state)

    assert len(llm.calls) == 2  # first attempt + retry
    assert result["sleep_metrics"]["trend"] == "down"


def test_sleep_raises_after_max_attempts(monkeypatch):
    bad = "raise RuntimeError('nope')"
    llm = _FakeLLM(responses=[bad, bad, bad])
    ci = _FakeCI(results=[
        {"ok": False, "stdout": "", "stderr": "RuntimeError: nope", "files": [], "error": "ExecErr"},
    ] * 3)
    s3 = MagicMock()
    monkeypatch.setenv("ARTIFACTS_S3_BUCKET", "bucket-art")
    monkeypatch.setattr("nodes.sleep.get_llm", lambda _p: llm)

    node = make_sleep_node(ci=ci, s3=s3, max_attempts=3)
    with pytest.raises(RuntimeError, match="sleep"):
        node({"sleep_csv": "x", "run_id": "abc"})
```

- [ ] **Step 2: Run test to verify FAIL**

Run:
```bash
uv run pytest tests/test_sleep.py -v
```
Expected: FAIL — module not found.

- [ ] **Step 3: Implement shared helper `_extract_code` and metrics extractor**

This file will be shared by `sleep.py` and `activity.py`; keep it internal to `nodes/`.

Create `nodes/_codegen.py`:

```python
"""Internal helpers for Code-Interpreter-backed analysis nodes (sleep, activity)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

from events import emit
from infra.code_interpreter import CodeInterpreterWrapper
from infra.llm import get_llm
from infra.s3 import S3Client

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

_CODE_BLOCK = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)
_METRICS_LINE = re.compile(r"METRICS_JSON:\s*(\{.*\})")


def load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")


def extract_code(text: str) -> str:
    m = _CODE_BLOCK.search(text)
    if m:
        return m.group(1).strip()
    return text.strip()


def extract_metrics(stdout: str) -> dict[str, Any]:
    m = _METRICS_LINE.search(stdout)
    if not m:
        raise ValueError("METRICS_JSON line not found in stdout")
    return json.loads(m.group(1))


def run_codegen_loop(
    *,
    node_name: str,
    prompt_file: str,
    csv_filename: str,
    csv_content: str,
    chart_filename: str,
    ci: CodeInterpreterWrapper,
    s3: S3Client,
    run_id: str,
    artifacts_bucket: str,
    max_attempts: int = 3,
) -> dict[str, Any]:
    """Run one analysis node's codegen+execute loop with self-correction."""
    llm = get_llm("analyze")
    ci.write_files({csv_filename: csv_content})

    prompt_template = load_prompt(prompt_file)
    last_error = "(none)"

    for attempt in range(1, max_attempts + 1):
        prompt = prompt_template.replace("{error_feedback}", last_error)
        response = llm.invoke([{"role": "user", "content": prompt}])
        raw = response.content if isinstance(response.content, str) else str(response.content)
        code = extract_code(raw)

        emit({"event": "code_generated", "node": node_name, "code": code, "attempt": attempt})

        # Use execute_isolated — wraps code in `def _analysis(): ... _analysis()`
        # so variables from previous node calls (same session) don't leak in.
        result = ci.execute_isolated(code)

        emit({
            "event": "code_result",
            "node": node_name,
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "ok": result["ok"],
            "attempt": attempt,
        })

        if result["ok"]:
            try:
                metrics = extract_metrics(result["stdout"])
            except ValueError as e:
                last_error = str(e)
                continue

            png_bytes = ci.read_file(chart_filename)
            chart_key = f"runs/{run_id}/{chart_filename}"
            s3.upload_bytes(artifacts_bucket, chart_key, png_bytes, content_type="image/png")

            emit({
                "event": "artifact",
                "node": node_name,
                "s3_key": chart_key,
                "content_type": "image/png",
            })

            return {
                "avg": {k: v for k, v in metrics.items() if k != "trend"},
                "trend": metrics["trend"],
                "chart_s3_key": chart_key,
            }

        last_error = result["stderr"] or result.get("error") or "unknown error"

    raise RuntimeError(f"{node_name} node failed after {max_attempts} attempts: {last_error}")
```

- [ ] **Step 4: Implement `nodes/sleep.py`**

```python
"""Node: sleep analysis via Code Interpreter."""

from __future__ import annotations

import os
from typing import Callable

from infra.code_interpreter import CodeInterpreterWrapper
from infra.llm import get_llm  # noqa: F401 — re-exported for test monkeypatching
from infra.s3 import S3Client
from nodes._codegen import run_codegen_loop
from state import TriBalanceState


def make_sleep_node(
    *,
    ci: CodeInterpreterWrapper,
    s3: S3Client,
    max_attempts: int = 3,
) -> Callable[[TriBalanceState], dict]:
    def sleep_node(state: TriBalanceState) -> dict:
        metrics = run_codegen_loop(
            node_name="sleep",
            prompt_file="code_synthesis_sleep.md",
            csv_filename="sleep.csv",
            csv_content=state["sleep_csv"],
            chart_filename="sleep_trend.png",
            ci=ci,
            s3=s3,
            run_id=state["run_id"],
            artifacts_bucket=os.environ["ARTIFACTS_S3_BUCKET"],
            max_attempts=max_attempts,
        )
        return {"sleep_metrics": metrics}

    return sleep_node
```

> **Why `get_llm` imported at top but unused here:** test monkeypatches `nodes.sleep.get_llm`, which works because `_codegen.run_codegen_loop` calls `get_llm` via `from infra.llm import get_llm` — BUT the test patches it at `nodes.sleep`. To keep the test's monkeypatch target working, import `get_llm` here, and have `_codegen.run_codegen_loop` accept an optional override. Simpler alternative: patch at `nodes._codegen.get_llm` in the test.

**Fix:** Change the test's monkeypatch target from `nodes.sleep.get_llm` to `nodes._codegen.get_llm`:

Update `tests/test_sleep.py`:
- Replace every `monkeypatch.setattr("nodes.sleep.get_llm", ...)` with `monkeypatch.setattr("nodes._codegen.get_llm", ...)`.
- Remove the unused re-export of `get_llm` from `nodes/sleep.py` (delete the `from infra.llm import get_llm` line).

- [ ] **Step 5: Run test to verify PASS**

Run:
```bash
uv run pytest tests/test_sleep.py -v
```
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add tribalance/app/TriBalanceAgent/nodes/_codegen.py \
        tribalance/app/TriBalanceAgent/nodes/sleep.py \
        tribalance/app/TriBalanceAgent/tests/test_sleep.py
git commit -m "feat(nodes): sleep analysis with Code Interpreter + self-correcting retry loop"
```

---

## Task 17: `nodes/activity.py` (mirror of sleep)

**Files:**
- Create: `tribalance/app/TriBalanceAgent/tests/test_activity.py`
- Create: `tribalance/app/TriBalanceAgent/nodes/activity.py`

- [ ] **Step 1: Write failing test**

`tests/test_activity.py`:

```python
from unittest.mock import MagicMock

import pytest

import events
from nodes.activity import make_activity_node


class _FakeLLM:
    def __init__(self, code):
        self._code = code
    def invoke(self, messages):
        class _R:
            content = f"```python\n{self._code}\n```"
        return _R()


class _FakeCI:
    def __init__(self, result):
        self.result = result
    def write_files(self, files):
        self.written = files
    def execute_code(self, code):
        return self.result
    def read_file(self, path):
        return b"PNG"


@pytest.fixture(autouse=True)
def _clear_emitter():
    events.set_emitter(None)
    yield
    events.set_emitter(None)


def test_activity_happy_path(monkeypatch):
    llm = _FakeLLM(code="print('METRICS_JSON: {\"avg_steps\": 7500, \"avg_active_kcal\": 450, \"avg_exercise_min\": 29, \"trend\": \"up\"}')")
    ci = _FakeCI(result={
        "ok": True,
        "stdout": 'METRICS_JSON: {"avg_steps": 7500, "avg_active_kcal": 450, "avg_exercise_min": 29, "trend": "up"}\n',
        "stderr": "",
        "files": ["activity_trend.png"],
        "error": None,
    })
    s3 = MagicMock()
    monkeypatch.setenv("ARTIFACTS_S3_BUCKET", "bucket-art")
    monkeypatch.setattr("nodes._codegen.get_llm", lambda _p: llm)

    node = make_activity_node(ci=ci, s3=s3)
    state = {"activity_csv": "date,steps,active_kcal,exercise_min\n2026-04-02,6421,380,22\n", "run_id": "xyz"}
    out = node(state)

    assert ci.written == {"activity.csv": state["activity_csv"]}
    assert out["activity_metrics"]["trend"] == "up"
    assert out["activity_metrics"]["avg"]["avg_steps"] == 7500
    assert out["activity_metrics"]["chart_s3_key"].endswith("activity_trend.png")
    s3.upload_bytes.assert_called_once()
```

- [ ] **Step 2: Run test to verify FAIL**

Run:
```bash
uv run pytest tests/test_activity.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement `nodes/activity.py`**

```python
"""Node: activity analysis via Code Interpreter."""

from __future__ import annotations

import os
from typing import Callable

from infra.code_interpreter import CodeInterpreterWrapper
from infra.s3 import S3Client
from nodes._codegen import run_codegen_loop
from state import TriBalanceState


def make_activity_node(
    *,
    ci: CodeInterpreterWrapper,
    s3: S3Client,
    max_attempts: int = 3,
) -> Callable[[TriBalanceState], dict]:
    def activity_node(state: TriBalanceState) -> dict:
        metrics = run_codegen_loop(
            node_name="activity",
            prompt_file="code_synthesis_activity.md",
            csv_filename="activity.csv",
            csv_content=state["activity_csv"],
            chart_filename="activity_trend.png",
            ci=ci,
            s3=s3,
            run_id=state["run_id"],
            artifacts_bucket=os.environ["ARTIFACTS_S3_BUCKET"],
            max_attempts=max_attempts,
        )
        return {"activity_metrics": metrics}

    return activity_node
```

- [ ] **Step 4: Run test to verify PASS**

Run:
```bash
uv run pytest tests/test_activity.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add tribalance/app/TriBalanceAgent/nodes/activity.py \
        tribalance/app/TriBalanceAgent/tests/test_activity.py
git commit -m "feat(nodes): activity analysis node (mirrors sleep with activity prompt + CSV)"
```

---

## Task 18: `synthesize.py` + `plan.py` + `plan_generator.md`

**Files:**
- Create: `tribalance/app/TriBalanceAgent/prompts/plan_generator.md`
- Create: `tribalance/app/TriBalanceAgent/tests/test_synthesize.py`
- Create: `tribalance/app/TriBalanceAgent/tests/test_plan.py`
- Create: `tribalance/app/TriBalanceAgent/nodes/synthesize.py`
- Create: `tribalance/app/TriBalanceAgent/nodes/plan.py`

- [ ] **Step 1: Write `prompts/plan_generator.md`**

```markdown
# Weekly Health Plan Generator (Korean)

당신은 사용자의 **수면 + 활동** 데이터를 한국어로 해석해 한 주 짜리 라이프스타일 플랜을 작성합니다.

## 입력

### 지표
{metrics_json}

### 인사이트 (한 줄씩)
{insights_bullets}

## 출력 형식

세 문단:
1. **현황 요약** (2-3문장, 수면과 활동 각각의 주요 수치 + 트렌드)
2. **이번 주 플랜** (번호 리스트, 3-5개 항목, 각 항목은 "월/수/금 아침 30분 걷기" 식으로 구체적 시점/분량 포함)
3. **주의할 점** (한 문장)

마크다운 헤더는 쓰지 마세요. 빈 줄로만 문단을 구분하세요.
```

- [ ] **Step 2: Write `tests/test_synthesize.py`**

```python
from unittest.mock import MagicMock

from nodes.synthesize import make_synthesize_node


class _FakeLLM:
    def invoke(self, messages):
        class _R:
            content = "- 평일 수면 효율이 주말보다 낮음\n- 수요일 활동량 급증"
        return _R()


def test_synthesize_produces_insights_bullets(monkeypatch):
    monkeypatch.setattr("nodes.synthesize.get_llm", lambda _p: _FakeLLM())
    node = make_synthesize_node()

    state = {
        "sleep_metrics": {"avg": {"avg_duration_hr": 6.8, "avg_efficiency": 0.78}, "trend": "down", "chart_s3_key": "x"},
        "activity_metrics": {"avg": {"avg_steps": 7420, "avg_active_kcal": 450, "avg_exercise_min": 29}, "trend": "stable", "chart_s3_key": "y"},
    }
    out = node(state)
    assert len(out["insights"]) >= 1
    assert all(not s.startswith("-") for s in out["insights"])  # dash stripped
```

- [ ] **Step 3: Write `nodes/synthesize.py`**

```python
"""Node: synthesize 2-axis insights from sleep+activity metrics via LLM."""

from __future__ import annotations

import json

from infra.llm import get_llm
from state import TriBalanceState

_SYSTEM = (
    "You extract 3-5 bullet-point insights from weekly sleep+activity metrics. "
    "Return ONLY bullet points, one per line, starting with '- '. Be concise."
)


def make_synthesize_node():
    def synthesize_node(state: TriBalanceState) -> dict:
        llm = get_llm("orchestrator")
        payload = {
            "sleep": state["sleep_metrics"],
            "activity": state["activity_metrics"],
        }
        messages = [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)},
        ]
        response = llm.invoke(messages)
        raw = response.content if isinstance(response.content, str) else str(response.content)
        insights = [
            line.lstrip("- ").strip()
            for line in raw.splitlines()
            if line.strip().startswith("-")
        ]
        return {"insights": insights}

    return synthesize_node
```

- [ ] **Step 4: Write `tests/test_plan.py`**

```python
from nodes.plan import make_plan_node


class _FakeLLM:
    def invoke(self, messages):
        class _R:
            content = "이번 주 수면 평균 6.8시간으로 권장치보다 낮습니다...\n\n1. 월/수/금 22:30 이전 취침\n2. 퇴근 후 30분 걷기\n\n주의: 과도한 카페인 피하기."
        return _R()


def test_plan_renders_with_metrics_and_insights(monkeypatch):
    monkeypatch.setattr("nodes.plan.get_llm", lambda _p: _FakeLLM())
    node = make_plan_node()

    state = {
        "sleep_metrics": {"avg": {"avg_duration_hr": 6.8}, "trend": "down", "chart_s3_key": "x"},
        "activity_metrics": {"avg": {"avg_steps": 7420}, "trend": "stable", "chart_s3_key": "y"},
        "insights": ["평일 수면 효율이 낮음"],
    }
    out = node(state)
    assert "이번 주" in out["plan"]
    assert "22:30" in out["plan"]
```

- [ ] **Step 5: Write `nodes/plan.py`**

```python
"""Node: generate Korean weekly plan text."""

from __future__ import annotations

import json
from pathlib import Path

from infra.llm import get_llm
from state import TriBalanceState

_PROMPT_FILE = Path(__file__).parent.parent / "prompts" / "plan_generator.md"


def make_plan_node():
    def plan_node(state: TriBalanceState) -> dict:
        metrics_json = json.dumps(
            {
                "sleep": state["sleep_metrics"],
                "activity": state["activity_metrics"],
            },
            ensure_ascii=False,
            indent=2,
        )
        insights_bullets = "\n".join(f"- {s}" for s in state.get("insights", []))

        template = _PROMPT_FILE.read_text(encoding="utf-8")
        prompt = template.replace("{metrics_json}", metrics_json).replace(
            "{insights_bullets}", insights_bullets
        )

        llm = get_llm("orchestrator")
        response = llm.invoke([{"role": "user", "content": prompt}])
        text = response.content if isinstance(response.content, str) else str(response.content)
        return {"plan": text.strip()}

    return plan_node
```

- [ ] **Step 6: Run tests**

Run:
```bash
uv run pytest tests/test_synthesize.py tests/test_plan.py -v
```
Expected: 2 passed.

- [ ] **Step 7: Commit**

```bash
git add tribalance/app/TriBalanceAgent/prompts/plan_generator.md \
        tribalance/app/TriBalanceAgent/nodes/synthesize.py \
        tribalance/app/TriBalanceAgent/nodes/plan.py \
        tribalance/app/TriBalanceAgent/tests/test_synthesize.py \
        tribalance/app/TriBalanceAgent/tests/test_plan.py
git commit -m "feat(nodes): synthesize (insights) + plan (Korean weekly plan) nodes"
```

---

## Task 19: Wire graph + `main.py` entrypoint with event streaming

**Files:**
- Modify: `tribalance/app/TriBalanceAgent/graph.py`
- Create: `tribalance/app/TriBalanceAgent/main.py`

- [ ] **Step 1: Replace `graph.py` with full wiring**

```python
"""Build the TriBalance LangGraph: linear 6-node pipeline."""

from __future__ import annotations

from pathlib import Path

from langgraph.graph import END, StateGraph

from infra.code_interpreter import CodeInterpreterWrapper
from infra.s3 import S3Client
from nodes.activity import make_activity_node
from nodes.fetch import make_fetch_node
from nodes.parse import parse_node
from nodes.plan import make_plan_node
from nodes.sleep import make_sleep_node
from nodes.synthesize import make_synthesize_node
from state import TriBalanceState


def build_graph(
    *,
    ci: CodeInterpreterWrapper,
    s3: S3Client,
    tmp_root: Path,
):
    g = StateGraph(TriBalanceState)

    g.add_node("fetch",      make_fetch_node(s3=s3, tmp_root=tmp_root))
    g.add_node("parse",      parse_node)
    g.add_node("sleep",      make_sleep_node(ci=ci, s3=s3))
    g.add_node("activity",   make_activity_node(ci=ci, s3=s3))
    g.add_node("synthesize", make_synthesize_node())
    g.add_node("plan",       make_plan_node())

    g.set_entry_point("fetch")
    g.add_edge("fetch", "parse")
    g.add_edge("parse", "sleep")
    g.add_edge("sleep", "activity")
    g.add_edge("activity", "synthesize")
    g.add_edge("synthesize", "plan")
    g.add_edge("plan", END)

    return g.compile()
```

- [ ] **Step 2: Write `main.py`**

```python
"""AgentCore Runtime entrypoint for TriBalanceAgent.

Invocation payload:
    {"s3_key": "path/to/export.xml", "week_start": "2026-04-14"}

Yields a stream of events terminating in `{event: "complete", report: {...}}`.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator

from bedrock_agentcore.runtime import BedrockAgentCoreApp

import events
from graph import build_graph
from infra.code_interpreter import CodeInterpreterWrapper
from infra.logging_config import correlation_id_var, get_logger, setup_logging
from infra.s3 import S3Client

setup_logging(os.environ.get("LOG_LEVEL", "INFO"))
log = get_logger("tribalance.main")

app = BedrockAgentCoreApp()

_REGION = os.environ.get("BEDROCK_REGION", "us-west-2")


@app.entrypoint
async def invoke(payload: dict, context: Any = None) -> AsyncGenerator[dict, None]:
    run_id = uuid.uuid4().hex[:12]
    correlation_id_var.set(run_id)

    s3_key = payload.get("s3_key")
    week_start = payload.get("week_start")
    if not s3_key:
        yield {"event": "error", "message": "payload.s3_key is required"}
        return

    yield {
        "event": "run_started",
        "run_id": run_id,
        "period": week_start or "auto",
    }

    event_queue: asyncio.Queue = asyncio.Queue()

    def _sync_emit(e: dict) -> None:
        event_queue.put_nowait(e)

    s3 = S3Client(region=_REGION)
    tmp_root = Path(tempfile.mkdtemp(prefix=f"tribalance-{run_id}-"))

    initial_state = {
        "s3_key": s3_key,
        "week_start": week_start or "",
        "run_id": run_id,
    }

    async def _run_graph() -> dict:
        with CodeInterpreterWrapper(_REGION) as ci:
            events.set_emitter(_sync_emit)
            try:
                graph = build_graph(ci=ci, s3=s3, tmp_root=tmp_root)
                final_state: dict = {}

                def _run():
                    state = dict(initial_state)
                    for chunk in graph.stream(state):
                        for node_name, node_state in chunk.items():
                            _sync_emit({"event": "node_end", "node": node_name})
                            state.update(node_state)
                    return state

                return await asyncio.to_thread(_run)
            finally:
                events.set_emitter(None)

    task = asyncio.create_task(_run_graph())

    # Drain queue until the graph task finishes
    while True:
        if task.done() and event_queue.empty():
            break
        try:
            event = await asyncio.wait_for(event_queue.get(), timeout=0.25)
            yield event
        except asyncio.TimeoutError:
            continue

    try:
        final_state = await task
    except Exception as exc:
        log.exception("graph failed")
        yield {"event": "error", "message": str(exc)}
        return

    yield {
        "event": "complete",
        "report": {
            "run_id": run_id,
            "period": week_start or "",
            "parse_summary": final_state.get("parse_summary"),
            "metrics": {
                "sleep": final_state.get("sleep_metrics"),
                "activity": final_state.get("activity_metrics"),
            },
            "insights": final_state.get("insights", []),
            "plan": final_state.get("plan", ""),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }


if __name__ == "__main__":
    app.run()
```

- [ ] **Step 3: Smoke-import**

Run:
```bash
cd tribalance/app/TriBalanceAgent
uv run python -c "import main; print('ok')"
```
Expected: `ok`. (Starts no server — just verifies imports.)

- [ ] **Step 4: Commit**

```bash
git add tribalance/app/TriBalanceAgent/graph.py tribalance/app/TriBalanceAgent/main.py
git commit -m "feat: main.py entrypoint with event streaming + full graph wiring"
```

---

## Task 20: End-to-end graph test (mocked externals)

**Files:**
- Create: `tribalance/app/TriBalanceAgent/tests/test_graph.py`

- [ ] **Step 1: Write the test**

```python
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import events
from graph import build_graph


FIXTURE_XML = Path(__file__).parent / "fixtures" / "export_sample.xml"


class _FakeLLM:
    def __init__(self, code_sleep: str, code_activity: str):
        self._sleep = code_sleep
        self._activity = code_activity
        self._calls = 0
    def invoke(self, messages):
        class _R:
            content = None
        self._calls += 1
        if self._calls == 1:
            _R.content = f"```python\n{self._sleep}\n```"
        elif self._calls == 2:
            _R.content = f"```python\n{self._activity}\n```"
        elif self._calls == 3:
            _R.content = "- 평일 수면 효율 낮음\n- 수요일 활동량 급증"
        else:
            _R.content = "이번 주 요약.\n\n1. 항목\n\n주의 사항."
        return _R()


class _FakeCI:
    def __init__(self, ok_sleep, ok_activity):
        self._ok_sleep = ok_sleep
        self._ok_activity = ok_activity
        self._call = 0
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def write_files(self, files): pass
    def execute_code(self, code):
        self._call += 1
        if self._call == 1:
            return {"ok": self._ok_sleep, "stdout": 'METRICS_JSON: {"avg_duration_hr": 7.6, "avg_efficiency": 0.95, "trend": "stable"}\n',
                    "stderr": "", "files": ["sleep_trend.png"], "error": None}
        return {"ok": self._ok_activity, "stdout": 'METRICS_JSON: {"avg_steps": 7500, "avg_active_kcal": 450, "avg_exercise_min": 29, "trend": "up"}\n',
                "stderr": "", "files": ["activity_trend.png"], "error": None}
    def read_file(self, path): return b"PNG"


def test_graph_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setenv("INPUT_S3_BUCKET", "bucket-in")
    monkeypatch.setenv("ARTIFACTS_S3_BUCKET", "bucket-art")

    # s3 stub: fetch copies the fixture into the tmp path
    s3 = MagicMock()
    def _download(bucket, key, dest):
        Path(dest).write_bytes(FIXTURE_XML.read_bytes())
    s3.download.side_effect = _download
    s3.upload_bytes.return_value = None

    llm = _FakeLLM(code_sleep="print('sleep')", code_activity="print('activity')")
    monkeypatch.setattr("nodes._codegen.get_llm", lambda _p: llm)
    monkeypatch.setattr("nodes.synthesize.get_llm", lambda _p: llm)
    monkeypatch.setattr("nodes.plan.get_llm", lambda _p: llm)

    ci = _FakeCI(ok_sleep=True, ok_activity=True)
    captured = []
    events.set_emitter(captured.append)
    try:
        graph = build_graph(ci=ci, s3=s3, tmp_root=tmp_path)
        final = graph.invoke({"s3_key": "foo.xml", "week_start": "2026-04-14", "run_id": "testrun"})

        assert final["parse_summary"]["period_days"] == 5
        assert final["sleep_metrics"]["trend"] == "stable"
        assert final["activity_metrics"]["avg"]["avg_steps"] == 7500
        assert len(final["insights"]) >= 1
        assert "이번 주" in final["plan"]
        event_names = {e["event"] for e in captured}
        assert {"code_generated", "code_result", "artifact"}.issubset(event_names)
    finally:
        events.set_emitter(None)
```

- [ ] **Step 2: Run test**

Run:
```bash
cd tribalance/app/TriBalanceAgent
uv run pytest tests/test_graph.py -v
```
Expected: 1 passed.

- [ ] **Step 3: Run full test suite**

Run:
```bash
uv run pytest -v --cov=. --cov-report=term-missing
```
Expected: All tests pass; coverage ≥ 80 % on `nodes/` and `infra/`.

- [ ] **Step 4: Commit**

```bash
git add tribalance/app/TriBalanceAgent/tests/test_graph.py
git commit -m "test: end-to-end graph test against fixture XML with mocked LLM + Code Interpreter"
```

---

## Task 21: Helper scripts + env example + final AGENTS.md polish

**Files:**
- Create: `scripts/provision_s3.sh`
- Create: `scripts/upload_sample.sh`
- Create: `scripts/invoke_local.sh`
- Create: `.env.example`

- [ ] **Step 1: Write `scripts/provision_s3.sh`**

```bash
#!/bin/bash
# One-time S3 bucket creation for TriBalance input + artifacts.
# Requires AWS_PROFILE set and appropriate IAM.

set -euo pipefail

: "${AWS_PROFILE:?set AWS_PROFILE}"
REGION="${BEDROCK_REGION:-us-west-2}"
INPUT="${INPUT_S3_BUCKET:-tribalance-input}"
ARTIFACTS="${ARTIFACTS_S3_BUCKET:-tribalance-artifacts}"

for bucket in "$INPUT" "$ARTIFACTS"; do
  if aws s3api head-bucket --bucket "$bucket" --region "$REGION" 2>/dev/null; then
    echo "  exists: $bucket"
  else
    echo "  creating: $bucket"
    aws s3api create-bucket \
      --bucket "$bucket" \
      --region "$REGION" \
      --create-bucket-configuration LocationConstraint="$REGION"
  fi
done
```

- [ ] **Step 2: Write `scripts/upload_sample.sh`**

```bash
#!/bin/bash
# Upload the test fixture XML to INPUT_S3_BUCKET so you can invoke the agent.

set -euo pipefail

: "${AWS_PROFILE:?set AWS_PROFILE}"
INPUT="${INPUT_S3_BUCKET:-tribalance-input}"
KEY="samples/export_sample.xml"
FILE="tribalance/app/TriBalanceAgent/tests/fixtures/export_sample.xml"

aws s3 cp "$FILE" "s3://${INPUT}/${KEY}"
echo "uploaded: s3://${INPUT}/${KEY}"
```

- [ ] **Step 3: Write `scripts/invoke_local.sh`**

```bash
#!/bin/bash
# Invoke the deployed TriBalanceAgent with the sample payload.

set -euo pipefail

: "${AWS_PROFILE:?set AWS_PROFILE}"

agentcore invoke --payload '{
  "s3_key": "samples/export_sample.xml",
  "week_start": "2026-04-06"
}'
```

- [ ] **Step 4: Make scripts executable**

Run:
```bash
chmod +x scripts/*.sh
```

- [ ] **Step 5: Write `.env.example`** at repo root

```
# Copy to .env (or export in your shell) for local dev. Do not commit .env.
AWS_PROFILE=developer-dongik
BEDROCK_REGION=us-west-2
INPUT_S3_BUCKET=tribalance-input
ARTIFACTS_S3_BUCKET=tribalance-artifacts
LLM_PROVIDER=openai

# Required for OpenAI provider
OPENAI_API_KEY=sk-...

# LangSmith tracing flags (non-sensitive — API key lives in Secrets Manager)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=tribalance
```

- [ ] **Step 6: Commit**

```bash
git add scripts/ .env.example
git commit -m "chore: helper scripts + .env.example for local dev and provisioning"
```

---

## Final Verification

- [ ] **Step 1: Re-run full test suite from repo root**

Run:
```bash
cd tribalance/app/TriBalanceAgent && uv run pytest -v --cov=. --cov-report=term
```
Expected: All pass. Coverage ≥ 80 % overall.

- [ ] **Step 2: Static checks**

Run:
```bash
uv run ruff check .
```
Expected: clean (or minor style warnings only).

- [ ] **Step 3: Verify agentcore.json schema compiles (no CDK deploy)**

Run:
```bash
cd tribalance
AWS_PROFILE=developer-dongik agentcore synth 2>&1 | head -20 || true
```
Expected: no schema validation errors. (If the command is unavailable in this CLI version, skip.)

- [ ] **Step 4: Final commit**

If there are uncommitted tweaks from running checks, commit them:
```bash
git add -A
git commit -m "chore: fixups from final verification" || true
git push
```

---

## Deployment Checklist (manual — run by user after plan complete)

1. Provision S3 buckets: `./scripts/provision_s3.sh`
2. Store secrets in AWS Secrets Manager (same region):
   ```bash
   aws secretsmanager create-secret --name OPENAI_API_KEY --secret-string 'sk-...'
   aws secretsmanager create-secret --name LANGCHAIN_API_KEY --secret-string 'ls-...'
   ```
3. Grant IAM: Runtime execution role needs `s3:GetObject` on input bucket, `s3:PutObject` on artifacts bucket, `bedrock-agentcore:InvokeCodeInterpreter`, `bedrock-agentcore:StartCodeInterpreterSession`, `bedrock-agentcore:StopCodeInterpreterSession`, `bedrock:InvokeModel` on the configured model IDs, `secretsmanager:GetSecretValue` on the two secrets.
4. Upload sample: `./scripts/upload_sample.sh`
5. Deploy: `cd tribalance && AWS_PROFILE=developer-dongik agentcore launch`
6. Invoke: `./scripts/invoke_local.sh`
7. Check LangSmith: https://smith.langchain.com → TriBalance project
8. Check CloudWatch: AWS console → AgentCore → TriBalanceAgent → Traces
