from pathlib import Path
from unittest.mock import MagicMock


import events
from graph import build_graph


FIXTURE_XML = Path(__file__).parent / "fixtures" / "export_sample.xml"


class _FakeLLM:
    def __init__(self, code_sleep: str, code_activity: str):
        self._sleep = code_sleep
        self._activity = code_activity
        self._calls = 0
    def invoke(self, messages):
        class _R:
            content = None
        self._calls += 1
        if self._calls == 1:
            _R.content = f"```python\n{self._sleep}\n```"
        elif self._calls == 2:
            _R.content = f"```python\n{self._activity}\n```"
        elif self._calls == 3:
            _R.content = "- 평일 수면 효율 낮음\n- 수요일 활동량 급증"
        else:
            _R.content = "이번 주 요약.\n\n1. 항목\n\n주의 사항."
        return _R()


class _FakeCI:
    def __init__(self, ok_sleep, ok_activity):
        self._ok_sleep = ok_sleep
        self._ok_activity = ok_activity
        self._call = 0
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def write_files(self, files): pass
    def execute_isolated(self, code):
        self._call += 1
        if self._call == 1:
            return {"ok": self._ok_sleep, "stdout": 'METRICS_JSON: {"avg_duration_hr": 7.6, "avg_efficiency": 0.95, "trend": "stable"}\n',
                    "stderr": "", "files": ["sleep_trend.png"], "error": None}
        return {"ok": self._ok_activity, "stdout": 'METRICS_JSON: {"avg_steps": 7500, "avg_active_kcal": 450, "avg_exercise_min": 29, "trend": "up"}\n',
                "stderr": "", "files": ["activity_trend.png"], "error": None}
    def read_file(self, path): return b"PNG"


def test_graph_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setenv("INPUT_S3_BUCKET", "bucket-in")
    monkeypatch.setenv("ARTIFACTS_S3_BUCKET", "bucket-art")

    # s3 stub: fetch copies the fixture into the tmp path
    s3 = MagicMock()
    def _download(bucket, key, dest):
        Path(dest).write_bytes(FIXTURE_XML.read_bytes())
    s3.download.side_effect = _download
    s3.upload_bytes.return_value = None

    llm = _FakeLLM(code_sleep="print('sleep')", code_activity="print('activity')")
    monkeypatch.setattr("nodes._codegen.get_llm", lambda _p: llm)
    monkeypatch.setattr("nodes.synthesize.get_llm", lambda _p: llm)
    monkeypatch.setattr("nodes.plan.get_llm", lambda _p: llm)

    ci = _FakeCI(ok_sleep=True, ok_activity=True)
    captured = []
    events.set_emitter(captured.append)
    try:
        graph = build_graph(ci=ci, s3=s3, tmp_root=tmp_path)
        final = graph.invoke({"s3_key": "foo.xml", "week_start": "2026-04-14", "run_id": "testrun"})

        assert final["parse_summary"]["period_days"] == 5
        assert final["sleep_metrics"]["trend"] == "stable"
        assert final["activity_metrics"]["avg"]["avg_steps"] == 7500
        assert len(final["insights"]) >= 1
        assert "이번 주" in final["plan"]
        event_names = {e["event"] for e in captured}
        assert {"code_generated", "code_result", "artifact"}.issubset(event_names)
    finally:
        events.set_emitter(None)
