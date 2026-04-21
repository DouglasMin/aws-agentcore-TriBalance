from unittest.mock import MagicMock


from infra.code_interpreter import CodeInterpreterWrapper


def _stream(events):
    """Match the AgentCore Code Interpreter stream shape."""
    return {"stream": [{"result": e} for e in events]}


def test_collect_stream_aggregates_stdout_stderr_files():
    response = _stream([
        {"stdout": "hello "},
        {"stdout": "world"},
        {"stderr": ""},
        {"files": ["chart.png"]},
    ])
    result = CodeInterpreterWrapper._collect_stream(response)
    assert result == {
        "stdout": "hello world",
        "stderr": "",
        "files": ["chart.png"],
        "ok": True,
        "error": None,
    }


def test_collect_stream_captures_error_and_stderr():
    response = _stream([
        {"stdout": ""},
        {"stderr": "NameError: name 'foo' is not defined"},
        {"error": "ExecutionError"},
    ])
    result = CodeInterpreterWrapper._collect_stream(response)
    assert result["ok"] is False
    assert "NameError" in result["stderr"]
    assert result["error"] == "ExecutionError"


def test_execute_code_calls_invoke_with_python():
    wrapper = CodeInterpreterWrapper.__new__(CodeInterpreterWrapper)
    wrapper._client = MagicMock()
    wrapper._client.invoke.return_value = _stream([{"stdout": "42\n"}])

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
    wrapper._client.invoke.return_value = _stream([{"stdout": "ok\n"}])

    wrapper.execute_isolated("x = 42\nprint('ok')")

    sent_code = wrapper._client.invoke.call_args.args[1]["code"]
    assert sent_code.startswith("def _analysis():")
    assert "    x = 42" in sent_code
    assert "    print('ok')" in sent_code
    assert sent_code.rstrip().endswith("_analysis()")
