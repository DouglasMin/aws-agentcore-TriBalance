from nodes.plan import make_plan_node


class _FakeLLM:
    def invoke(self, messages):
        class _R:
            content = "이번 주 수면 평균 6.8시간으로 권장치보다 낮습니다...\n\n1. 월/수/금 22:30 이전 취침\n2. 퇴근 후 30분 걷기\n\n주의: 과도한 카페인 피하기."
        return _R()


def test_plan_renders_with_metrics_and_insights(monkeypatch):
    monkeypatch.setattr("nodes.plan.get_llm", lambda _p: _FakeLLM())
    node = make_plan_node()

    state = {
        "sleep_metrics": {"avg": {"avg_duration_hr": 6.8}, "trend": "down", "chart_s3_key": "x"},
        "activity_metrics": {"avg": {"avg_steps": 7420}, "trend": "stable", "chart_s3_key": "y"},
        "insights": ["평일 수면 효율이 낮음"],
    }
    out = node(state)
    assert "이번 주" in out["plan"]
    assert "22:30" in out["plan"]
