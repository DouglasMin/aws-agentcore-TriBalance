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
