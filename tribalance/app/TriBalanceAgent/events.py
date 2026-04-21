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
