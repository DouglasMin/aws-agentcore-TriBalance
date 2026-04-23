"""Build the TriBalance LangGraph: linear 6-node pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from langgraph.graph import END, StateGraph

from events import emit
from infra.code_interpreter import CodeInterpreterWrapper
from infra.s3 import S3Client
from nodes.activity import make_activity_node
from nodes.fetch import make_fetch_node
from nodes.parse import parse_node
from nodes.plan import make_plan_node
from nodes.sleep import make_sleep_node
from nodes.synthesize import make_synthesize_node
from state import TriBalanceState


def _with_start_event(name: str, fn: Callable) -> Callable:
    """Emit ``node_start`` before the node runs so the UI can mark the
    pipeline dot active without waiting for the previous node's ``node_end``.
    Improves live-wait fidelity (especially for long-running nodes like
    ``sleep``/``activity`` where the Code Interpreter can take 3-6s)."""

    def wrapped(state):
        emit({"event": "node_start", "node": name})
        return fn(state)

    return wrapped


def build_graph(
    *,
    ci: CodeInterpreterWrapper,
    s3: S3Client,
    tmp_root: Path,
):
    g = StateGraph(TriBalanceState)

    g.add_node("fetch",      _with_start_event("fetch",      make_fetch_node(s3=s3, tmp_root=tmp_root)))
    g.add_node("parse",      _with_start_event("parse",      parse_node))
    g.add_node("sleep",      _with_start_event("sleep",      make_sleep_node(ci=ci, s3=s3)))
    g.add_node("activity",   _with_start_event("activity",   make_activity_node(ci=ci, s3=s3)))
    g.add_node("synthesize", _with_start_event("synthesize", make_synthesize_node()))
    g.add_node("plan",       _with_start_event("plan",       make_plan_node()))

    g.set_entry_point("fetch")
    g.add_edge("fetch", "parse")
    g.add_edge("parse", "sleep")
    g.add_edge("sleep", "activity")
    g.add_edge("activity", "synthesize")
    g.add_edge("synthesize", "plan")
    g.add_edge("plan", END)

    return g.compile()
