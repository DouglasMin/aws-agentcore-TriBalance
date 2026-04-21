from unittest.mock import MagicMock

from nodes.synthesize import make_synthesize_node


class _FakeLLM:
    def invoke(self, messages):
        class _R:
            content = "- 평일 수면 효율이 주말보다 낮음\n- 수요일 활동량 급증"
        return _R()


def test_synthesize_produces_insights_bullets(monkeypatch):
    monkeypatch.setattr("nodes.synthesize.get_llm", lambda _p: _FakeLLM())
    node = make_synthesize_node()

    state = {
        "sleep_metrics": {"avg": {"avg_duration_hr": 6.8, "avg_efficiency": 0.78}, "trend": "down", "chart_s3_key": "x"},
        "activity_metrics": {"avg": {"avg_steps": 7420, "avg_active_kcal": 450, "avg_exercise_min": 29}, "trend": "stable", "chart_s3_key": "y"},
    }
    out = node(state)
    assert len(out["insights"]) >= 1
    assert all(not s.startswith("-") for s in out["insights"])  # dash stripped
