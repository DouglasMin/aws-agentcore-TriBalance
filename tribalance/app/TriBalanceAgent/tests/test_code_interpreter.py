from unittest.mock import MagicMock


from infra.code_interpreter import CodeInterpreterWrapper


def _stream_sc(structured, *, is_error=False, content=None):
    """Build a fake executeCode response event with real AgentCore shape:
      { "result": { "structuredContent": {...}, "content": [...], "isError": bool } }
    """
    event = {
        "result": {
            "structuredContent": structured,
            "content": content or [],
            "isError": is_error,
        }
    }
    return {"stream": [event]}


def test_collect_stream_reads_stdout_and_stderr_from_structured_content():
    response = _stream_sc(
        {"stdout": "hello world", "stderr": "", "exitCode": 0}
    )
    result = CodeInterpreterWrapper._collect_stream(response)
    assert result == {
        "stdout": "hello world",
        "stderr": "",
        "files": [],
        "ok": True,
        "error": None,
    }


def test_collect_stream_sets_ok_false_on_is_error_or_nonzero_exit():
    response = _stream_sc(
        {"stdout": "", "stderr": "Traceback ... NameError: name 'foo'", "exitCode": 1},
        is_error=True,
    )
    result = CodeInterpreterWrapper._collect_stream(response)
    assert result["ok"] is False
    assert "NameError" in result["stderr"]
    assert result["error"] == "code execution failed"


def test_collect_stream_extracts_chart_files_from_content_resources():
    response = _stream_sc(
        {"stdout": "done", "stderr": "", "exitCode": 0},
        content=[
            {"type": "text", "text": "done"},
            {"type": "resource", "resource": {"uri": "file:///sandbox/sleep_trend.png"}},
        ],
    )
    result = CodeInterpreterWrapper._collect_stream(response)
    assert result["files"] == ["/sandbox/sleep_trend.png"]


def test_execute_code_calls_invoke_with_python():
    wrapper = CodeInterpreterWrapper.__new__(CodeInterpreterWrapper)
    wrapper._client = MagicMock()
    wrapper._client.invoke.return_value = _stream_sc(
        {"stdout": "42\n", "stderr": "", "exitCode": 0}
    )

    result = wrapper.execute_code("print(6*7)")

    wrapper._client.invoke.assert_called_once_with(
        "executeCode",
        {"language": "python", "code": "print(6*7)"},
    )
    assert result["stdout"] == "42\n"
    assert result["ok"] is True


def test_write_files_converts_dict_to_content_list():
    wrapper = CodeInterpreterWrapper.__new__(CodeInterpreterWrapper)
    wrapper._client = MagicMock()

    wrapper.write_files({"a.csv": "x,y\n1,2\n", "b.py": "print(1)"})

    call = wrapper._client.invoke.call_args
    assert call.args[0] == "writeFiles"
    content = call.args[1]["content"]
    assert {c["path"] for c in content} == {"a.csv", "b.py"}


def test_context_manager_starts_and_stops(monkeypatch):
    created = []

    class FakeClient:
        def __init__(self, region):
            created.append(region)
            self.started = False
            self.stopped = False

        def start(self):
            self.started = True

        def stop(self):
            self.stopped = True

    monkeypatch.setattr(
        "infra.code_interpreter.CodeInterpreter", FakeClient
    )

    with CodeInterpreterWrapper("ap-northeast-2") as w:
        assert w._client.started is True

    assert w._client.stopped is True
    assert created == ["ap-northeast-2"]


def test_execute_isolated_wraps_code_in_function_scope():
    wrapper = CodeInterpreterWrapper.__new__(CodeInterpreterWrapper)
    wrapper._client = MagicMock()
    wrapper._client.invoke.return_value = _stream_sc(
        {"stdout": "ok\n", "stderr": "", "exitCode": 0}
    )

    wrapper.execute_isolated("x = 42\nprint('ok')")

    sent_code = wrapper._client.invoke.call_args.args[1]["code"]
    assert sent_code.startswith("def _analysis():")
    assert "    x = 42" in sent_code
    assert "    print('ok')" in sent_code
    assert sent_code.rstrip().endswith("_analysis()")
