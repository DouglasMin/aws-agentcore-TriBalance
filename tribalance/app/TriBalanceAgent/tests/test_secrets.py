import json
from unittest.mock import MagicMock

import pytest

from infra import secrets


@pytest.fixture(autouse=True)
def _clear_cache():
    secrets._cache.clear()
    yield
    secrets._cache.clear()


def test_get_secret_returns_plain_string(monkeypatch):
    mock_client = MagicMock()
    mock_client.get_secret_value.return_value = {"SecretString": "sk-plain"}
    monkeypatch.setattr(secrets, "_client", lambda: mock_client)

    assert secrets.get_secret("MY_KEY") == "sk-plain"


def test_get_secret_extracts_json_field(monkeypatch):
    mock_client = MagicMock()
    mock_client.get_secret_value.return_value = {
        "SecretString": json.dumps({"MY_KEY": "sk-json"})
    }
    monkeypatch.setattr(secrets, "_client", lambda: mock_client)

    assert secrets.get_secret("MY_KEY") == "sk-json"


def test_get_secret_cached(monkeypatch):
    mock_client = MagicMock()
    mock_client.get_secret_value.return_value = {"SecretString": "sk-cache"}
    monkeypatch.setattr(secrets, "_client", lambda: mock_client)

    secrets.get_secret("K")
    secrets.get_secret("K")

    assert mock_client.get_secret_value.call_count == 1


def test_get_secret_prefers_env_var(monkeypatch):
    monkeypatch.setenv("FROM_ENV", "env-value")
    assert secrets.get_secret("FROM_ENV") == "env-value"
