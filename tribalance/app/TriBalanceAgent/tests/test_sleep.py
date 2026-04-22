from unittest.mock import MagicMock

import pytest

import events
from nodes.sleep import make_sleep_node


class _FakeLLM:
    """Returns successive canned code strings as the LLM response."""
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        code = self.responses.pop(0)
        class _Resp:
            content = f"```python\n{code}\n```"
        return _Resp()


class _FakeCI:
    def __init__(self, results):
        self.results = list(results)
        self.writes = []
        self.reads = []

    def write_files(self, files):
        self.writes.append(files)

    def execute_isolated(self, code):
        return self.results.pop(0)

    def read_file(self, path):
        self.reads.append(path)
        return b"FAKEPNG"


@pytest.fixture(autouse=True)
def _clear_emitter():
    events.set_emitter(None)
    yield
    events.set_emitter(None)


def test_sleep_happy_path(monkeypatch):
    llm = _FakeLLM(responses=["print('METRICS_JSON: {\"avg_duration_hr\": 7.6, \"avg_efficiency\": 0.95, \"trend\": \"stable\"}')"])
    ci = _FakeCI(results=[{
        "ok": True,
        "stdout": 'METRICS_JSON: {"avg_duration_hr": 7.6, "avg_efficiency": 0.95, "trend": "stable"}\n',
        "stderr": "",
        "files": ["sleep_trend.png"],
        "error": None,
    }])
    s3 = MagicMock()
    monkeypatch.setenv("ARTIFACTS_S3_BUCKET", "bucket-art")
    monkeypatch.setattr("nodes._codegen.get_llm", lambda _p: llm)

    captured = []
    events.set_emitter(captured.append)

    node = make_sleep_node(ci=ci, s3=s3)
    state = {"sleep_csv": "date,in_bed_min,asleep_min\n2026-04-02,475,455\n", "run_id": "abc"}
    result = node(state)

    # writeFiles called with sleep.csv
    assert ci.writes[0] == {"sleep.csv": state["sleep_csv"]}
    # metrics extracted from METRICS_JSON line
    m = result["sleep_metrics"]
    assert m["avg"]["avg_duration_hr"] == 7.6
    assert m["trend"] == "stable"
    assert m["chart_s3_key"].endswith("sleep_trend.png")
    # s3 upload happened
    s3.upload_bytes.assert_called_once()
    # events streamed
    event_names = [e["event"] for e in captured]
    assert "code_generated" in event_names
    assert "code_result" in event_names
    assert "artifact" in event_names


def test_sleep_retries_on_failure_then_succeeds(monkeypatch):
    bad = "raise ValueError('boom')"
    good = "print('METRICS_JSON: {\"avg_duration_hr\": 6.0, \"avg_efficiency\": 0.8, \"trend\": \"down\"}')"
    llm = _FakeLLM(responses=[bad, good])
    ci = _FakeCI(results=[
        {"ok": False, "stdout": "", "stderr": "ValueError: boom", "files": [], "error": "ExecErr"},
        {"ok": True, "stdout": 'METRICS_JSON: {"avg_duration_hr": 6.0, "avg_efficiency": 0.8, "trend": "down"}\n',
         "stderr": "", "files": ["sleep_trend.png"], "error": None},
    ])
    s3 = MagicMock()
    monkeypatch.setenv("ARTIFACTS_S3_BUCKET", "bucket-art")
    monkeypatch.setattr("nodes._codegen.get_llm", lambda _p: llm)

    node = make_sleep_node(ci=ci, s3=s3)
    state = {"sleep_csv": "date,in_bed_min,asleep_min\n2026-04-02,475,455\n", "run_id": "abc"}
    result = node(state)

    assert len(llm.calls) == 2  # first attempt + retry
    assert result["sleep_metrics"]["trend"] == "down"


def test_sleep_raises_after_max_attempts(monkeypatch):
    bad = "raise RuntimeError('nope')"
    llm = _FakeLLM(responses=[bad, bad, bad])
    ci = _FakeCI(results=[
        {"ok": False, "stdout": "", "stderr": "RuntimeError: nope", "files": [], "error": "ExecErr"},
    ] * 3)
    s3 = MagicMock()
    monkeypatch.setenv("ARTIFACTS_S3_BUCKET", "bucket-art")
    monkeypatch.setattr("nodes._codegen.get_llm", lambda _p: llm)

    node = make_sleep_node(ci=ci, s3=s3, max_attempts=3)
    with pytest.raises(RuntimeError, match="sleep"):
        node({"sleep_csv": "x", "run_id": "abc"})


def test_sleep_emits_metrics_event(monkeypatch):
    llm = _FakeLLM(responses=["print('METRICS_JSON: {\"avg_duration_hr\": 7.6, \"avg_efficiency\": 0.95, \"trend\": \"stable\"}')"])
    ci = _FakeCI(results=[{
        "ok": True,
        "stdout": 'METRICS_JSON: {"avg_duration_hr": 7.6, "avg_efficiency": 0.95, "trend": "stable"}\n',
        "stderr": "", "files": ["sleep_trend.png"], "error": None,
    }])
    s3 = MagicMock()
    monkeypatch.setenv("ARTIFACTS_S3_BUCKET", "bucket-art")
    monkeypatch.setattr("nodes._codegen.get_llm", lambda _p: llm)

    captured = []
    events.set_emitter(captured.append)

    node = make_sleep_node(ci=ci, s3=s3)
    state = {"sleep_csv": "date,in_bed_min,asleep_min\n2026-04-02,475,455\n", "run_id": "abc"}
    node(state)

    metrics_events = [e for e in captured if e.get("event") == "metrics"]
    assert len(metrics_events) == 1
    assert metrics_events[0]["node"] == "sleep"
    assert metrics_events[0]["metrics"]["avg_duration_hr"] == 7.6
    assert metrics_events[0]["metrics"]["trend"] == "stable"


def test_sleep_retries_when_read_file_fails_after_metrics(monkeypatch):
    """If ci.read_file raises after metrics are extracted, loop retries rather
    than leaving an orphaned metrics event without an artifact."""
    llm = _FakeLLM(responses=[
        "print('METRICS_JSON: {\"avg_duration_hr\": 7.6, \"avg_efficiency\": 0.95, \"trend\": \"stable\"}')",
        "print('METRICS_JSON: {\"avg_duration_hr\": 7.6, \"avg_efficiency\": 0.95, \"trend\": \"stable\"}')",
    ])

    class _FlakyCI:
        def __init__(self):
            self.read_calls = 0

        def write_files(self, files): pass
        def execute_isolated(self, code):
            return {
                "ok": True,
                "stdout": 'METRICS_JSON: {"avg_duration_hr": 7.6, "avg_efficiency": 0.95, "trend": "stable"}\n',
                "stderr": "", "files": ["sleep_trend.png"], "error": None,
            }
        def read_file(self, path):
            self.read_calls += 1
            if self.read_calls == 1:
                raise IOError("transient network failure")
            return b"PNG"

    ci = _FlakyCI()
    s3 = MagicMock()
    monkeypatch.setenv("ARTIFACTS_S3_BUCKET", "bucket-art")
    monkeypatch.setattr("nodes._codegen.get_llm", lambda _p: llm)

    captured = []
    events.set_emitter(captured.append)

    node = make_sleep_node(ci=ci, s3=s3)
    result = node({"sleep_csv": "x", "run_id": "abc"})

    # Succeeded on attempt 2
    assert ci.read_calls == 2
    metrics_events = [e for e in captured if e.get("event") == "metrics"]
    artifact_events = [e for e in captured if e.get("event") == "artifact"]
    # Two metrics emits (one per attempt), one artifact (only successful attempt)
    assert len(metrics_events) == 2
    assert len(artifact_events) == 1
    assert result["sleep_metrics"]["trend"] == "stable"
