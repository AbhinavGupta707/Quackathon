from __future__ import annotations

import json

import httpx
import pytest

from app.config import Settings
from app.providers.fireworks import FireworksProviderError, FireworksReasoningAdapter


def _settings() -> Settings:
    return Settings(
        environment="test",
        fireworks_base_url="https://fireworks.test/inference/v1",
        fireworks_api_key="fireworks-secret-key",
        fireworks_model="accounts/fireworks/models/test-model",
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
