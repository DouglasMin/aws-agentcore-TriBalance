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

    with tempfile.TemporaryDirectory(prefix=f"tribalance-{run_id}-") as _tmp:
        tmp_root = Path(_tmp)

        event_queue: asyncio.Queue = asyncio.Queue()

        def _sync_emit(e: dict) -> None:
            event_queue.put_nowait(e)

        s3 = S3Client(region=_REGION)

        initial_state = {
            "s3_key": s3_key,
            "week_start": week_start or "",
            "run_id": run_id,
        }

        async def _run_graph() -> dict:
            with CodeInterpreterWrapper(_REGION) as ci:
                graph = build_graph(ci=ci, s3=s3, tmp_root=tmp_root)

                def _run():
                    # Set emitter inside the worker thread so its ContextVar
                    # binding lives in the thread's own context copy. Nodes
                    # invoked from graph.stream() run in this same thread and
                    # read back the emitter via events.emit().
                    events.set_emitter(_sync_emit)
                    try:
                        state = dict(initial_state)
                        for chunk in graph.stream(state):
                            for node_name, node_state in chunk.items():
                                _sync_emit({"event": "node_end", "node": node_name})
                                state.update(node_state)
                        return state
                    finally:
                        events.set_emitter(None)

                return await asyncio.to_thread(_run)

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
