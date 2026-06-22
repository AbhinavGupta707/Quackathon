from __future__ import annotations

from contextlib import contextmanager
import json
from typing import Any

import httpx
import pytest

from app.config import Settings
import app.providers.fireworks as fireworks_module
from app.providers.fireworks import FireworksProviderError, FireworksReasoningAdapter


def _settings() -> Settings:
    return Settings(
        environment="test",
        fireworks_base_url="https://fireworks.test/inference/v1",
        fireworks_api_key="fireworks-secret-key",
        fireworks_model="accounts/fireworks/models/test-model",
    )


def _traced_settings() -> Settings:
    return Settings(
        environment="test",
        fireworks_base_url="https://fireworks.test/inference/v1",
        fireworks_api_key="fireworks-secret-key",
        fireworks_model="accounts/fireworks/models/test-model",
        langsmith_tracing=True,
        langsmith_api_key="langsmith-secret-key",
        langsmith_trace_content=False,
    )


@pytest.mark.asyncio
async def test_fireworks_adapter_uses_openai_compatible_structured_endpoint_without_leaking_secret() -> None:
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "intent": "object_location",
                                    "object_key": "keys",
                                    "confidence": "high",
                                }
                            )
                        }
                    }
                ]
            },
        )

    adapter = FireworksReasoningAdapter(
        _settings(),
        transport=httpx.MockTransport(handler),
    )

    result = await adapter.route_query(
        query="Where are my keys?",
        known_object_keys=["keys"],
    )

    assert result.intent == "object_location"
    assert result.object_key == "keys"
    assert captured_request is not None
    assert captured_request.url.path == "/inference/v1/chat/completions"
    assert captured_request.headers["authorization"] == "Bearer fireworks-secret-key"
    body = json.loads(captured_request.content.decode("utf-8"))
    assert body["response_format"]["type"] == "json_schema"
    assert "fireworks-secret-key" not in repr(result)


@pytest.mark.asyncio
async def test_fireworks_adapter_errors_do_not_include_api_key_or_response_body() -> None:
    adapter = FireworksReasoningAdapter(
        _settings(),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(500, json={"detail": "fireworks-secret-key"})
        ),
    )

    with pytest.raises(FireworksProviderError) as exc_info:
        await adapter.route_query(query="Where are my keys?", known_object_keys=["keys"])

    error_text = str(exc_info.value)
    assert "HTTP 500" in error_text
    assert "fireworks-secret-key" not in error_text


@pytest.mark.asyncio
async def test_fireworks_adapter_adds_privacy_safe_langsmith_trace(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    @contextmanager
    def fake_trace(settings: Settings, name: str, **kwargs: Any) -> Any:
        captured["name"] = name
        captured["inputs"] = kwargs["inputs"]
        captured["metadata"] = kwargs["metadata"]
        captured["tags"] = kwargs["tags"]
        yield object()

    def fake_add_outputs(run: object, outputs: dict[str, Any], *, include_content: bool = False) -> None:
        captured["outputs"] = outputs
        captured["include_content"] = include_content

    monkeypatch.setattr(fireworks_module, "langsmith_trace", fake_trace)
    monkeypatch.setattr(fireworks_module, "add_trace_outputs", fake_add_outputs)

    adapter = FireworksReasoningAdapter(
        _traced_settings(),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "intent": "object_location",
                                        "object_key": "keys",
                                        "confidence": "high",
                                    }
                                )
                            }
                        }
                    ],
                    "usage": {"total_tokens": 42},
                },
            )
        ),
    )

    result = await adapter.route_query(
        query="Where are my keys?",
        known_object_keys=["keys"],
    )

    assert result.object_key == "keys"
    assert captured["name"] == "fireworks.query_routing"
    assert captured["inputs"]["provider"] == "fireworks"
    assert captured["inputs"]["schema_name"] == "query_routing"
    assert "messages" not in captured["inputs"]
    assert captured["metadata"]["schema_name"] == "query_routing"
    assert captured["outputs"]["parsed_keys"] == ["confidence", "intent", "object_key"]
    assert captured["outputs"]["usage"] == {"total_tokens": 42}
    assert captured["outputs"]["content"] is None
    assert captured["include_content"] is False
