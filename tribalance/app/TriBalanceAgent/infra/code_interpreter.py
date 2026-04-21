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
