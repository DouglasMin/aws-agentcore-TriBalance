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
    def execute_isolated(self, code):
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


def test_activity_emits_metrics_event(monkeypatch):
    llm = _FakeLLM(code="print('METRICS_JSON: {\"avg_steps\": 7500, \"avg_active_kcal\": 450, \"avg_exercise_min\": 29, \"trend\": \"up\"}')")
    ci = _FakeCI(result={
        "ok": True,
        "stdout": 'METRICS_JSON: {"avg_steps": 7500, "avg_active_kcal": 450, "avg_exercise_min": 29, "trend": "up"}\n',
        "stderr": "", "files": ["activity_trend.png"], "error": None,
    })
    s3 = MagicMock()
    monkeypatch.setenv("ARTIFACTS_S3_BUCKET", "bucket-art")
    monkeypatch.setattr("nodes._codegen.get_llm", lambda _p: llm)

    captured = []
    events.set_emitter(captured.append)

    node = make_activity_node(ci=ci, s3=s3)
    state = {"activity_csv": "date,steps,active_kcal,exercise_min\n2026-04-02,7500,450,29\n", "run_id": "xyz"}
    node(state)

    metrics_events = [e for e in captured if e.get("event") == "metrics"]
    assert len(metrics_events) == 1
    assert metrics_events[0]["node"] == "activity"
    assert metrics_events[0]["metrics"]["avg_steps"] == 7500
