import pytest

from infra import llm


def test_get_provider_default(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert llm.get_provider() == "openai"


def test_get_provider_bedrock(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    assert llm.get_provider() == "bedrock"


def test_get_provider_case_insensitive(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "OpenAI")
    assert llm.get_provider() == "openai"


def test_get_llm_openai(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setattr("infra.llm.get_secret", lambda k: "sk-test")
    model = llm.get_llm("orchestrator")
    from langchain_openai import ChatOpenAI
    assert isinstance(model, ChatOpenAI)


def test_get_llm_bedrock(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    monkeypatch.setenv("BEDROCK_REGION", "us-west-2")
    model = llm.get_llm("analyze")
    from langchain_aws import ChatBedrockConverse
    assert isinstance(model, ChatBedrockConverse)


def test_get_llm_model_override(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("ANALYZE_MODEL", "gpt-5-override")
    monkeypatch.setattr("infra.llm.get_secret", lambda k: "sk-test")
    model = llm.get_llm("analyze")
    assert model.model_name == "gpt-5-override"


def test_get_llm_unknown_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mars")
    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
        llm.get_llm("orchestrator")
