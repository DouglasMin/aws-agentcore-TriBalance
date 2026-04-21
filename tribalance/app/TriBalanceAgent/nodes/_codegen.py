"""Internal helpers for Code-Interpreter-backed analysis nodes (sleep, activity)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

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
