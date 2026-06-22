from __future__ import annotations

import os

import pytest


_OPTIONAL_PROVIDER_ENV_DEFAULTS = {
    "FIREWORKS_API_KEY": "",
    "FIREWORKS_MODEL": "accounts/fireworks/models/deepseek-v4-flash",
    "LANGSMITH_TRACING": "false",
    "LANGSMITH_API_KEY": "",
    "LANGSMITH_PROJECT": "afferens-memory-guardian-test",
    "GEMINI_API_KEY": "",
    "PARCLE_API_KEY": "",
    "PARCEL_API_KEY": "",
}

for _name, _value in _OPTIONAL_PROVIDER_ENV_DEFAULTS.items():
    os.environ[_name] = _value


@pytest.fixture(autouse=True)
def isolate_optional_provider_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests deterministic even when the developer's local .env has live keys."""

    for name, value in _OPTIONAL_PROVIDER_ENV_DEFAULTS.items():
        monkeypatch.setenv(name, value)
