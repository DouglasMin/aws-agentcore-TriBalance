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
