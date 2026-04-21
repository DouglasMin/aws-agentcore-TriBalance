"""AWS Secrets Manager helper with env-var fallback and in-process cache."""

from __future__ import annotations

import json
import os
from functools import lru_cache

import boto3

_cache: dict[str, str] = {}


@lru_cache(maxsize=1)
def _client():
    region = os.environ.get("SECRETS_REGION", os.environ.get("BEDROCK_REGION", "ap-northeast-2"))
    return boto3.client("secretsmanager", region_name=region)


def get_secret(name: str) -> str:
    """Return the secret value for `name`.

    Lookup order:
      1. Process env var named `name` (for local dev)
      2. In-process cache
      3. AWS Secrets Manager (SecretString plain, or JSON field `name`)
    """
    env_value = os.environ.get(name)
    if env_value:
        return env_value

    if name in _cache:
        return _cache[name]

    response = _client().get_secret_value(SecretId=name)
    raw = response["SecretString"]

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and name in parsed:
            value = parsed[name]
        else:
            value = raw
    except json.JSONDecodeError:
        value = raw

    _cache[name] = value
    return value
