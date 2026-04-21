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
            region_name=os.environ.get("BEDROCK_REGION", "ap-northeast-2"),
            max_retries=2,
        )
    raise ValueError(f"Unknown LLM_PROVIDER: {provider}")
