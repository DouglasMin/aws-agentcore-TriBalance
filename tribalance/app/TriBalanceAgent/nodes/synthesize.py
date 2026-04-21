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
