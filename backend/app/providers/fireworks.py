from __future__ import annotations

import json
from typing import Any

import httpx
from pydantic import BaseModel, Field

from app.config import Settings
from app.schemas import QueryConfidence, QueryIntent, ServiceHealthState, ServiceStatus


class FireworksProviderUnavailable(RuntimeError):
    pass


class FireworksProviderError(RuntimeError):
    pass


class QueryRoutingResult(BaseModel):
    intent: QueryIntent = QueryIntent.UNKNOWN
    object_key: str | None = None
    confidence: QueryConfidence = QueryConfidence.LOW


class EvidenceSufficiencyResult(BaseModel):
    sufficient: bool
    confidence: QueryConfidence = QueryConfidence.LOW
    needs_human_verification: bool = True
    reason: str = Field(default="")


class AnswerSynthesisResult(BaseModel):
    answer: str
    confidence: QueryConfidence
    needs_human_verification: bool = True


class FireworksReasoningAdapter:
    """Structured-output adapter for Fireworks' OpenAI-compatible endpoint."""

    provider_name = "fireworks"

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    def status(self) -> ServiceStatus:
        if not self._settings.fireworks_configured:
            return ServiceStatus(
                state=ServiceHealthState.DEGRADED,
                message="Fireworks API key is not configured; deterministic fallback is available.",
            )
        return ServiceStatus(
            state=ServiceHealthState.OK,
            message="Fireworks key is configured for structured reasoning calls.",
        )

    async def route_query(
        self,
        *,
        query: str,
        known_object_keys: list[str],
    ) -> QueryRoutingResult:
        payload = await self._chat_json(
            schema_name="query_routing",
            response_model=QueryRoutingResult,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Classify the user query for an assistive home-memory prototype. "
                        "Return object_location only when the user asks where an object is. "
                        "Use object_key only from the provided known_object_keys when possible. "
                        "Do not invent objects."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "query": query,
                            "known_object_keys": known_object_keys,
                        }
                    ),
                },
            ],
        )
        return QueryRoutingResult.model_validate(payload)

    async def assess_evidence(
        self,
        *,
        query: str,
        object_key: str,
        evidence: dict[str, Any],
    ) -> EvidenceSufficiencyResult:
        payload = await self._chat_json(
            schema_name="evidence_sufficiency",
            response_model=EvidenceSufficiencyResult,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Assess whether the provided structured Afferens evidence is enough "
                        "to answer the object-location question. Be conservative. "
                        "If there is no cited observation evidence, mark sufficient false."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "query": query,
                            "object_key": object_key,
                            "evidence": evidence,
                        },
                        default=str,
                    ),
                },
            ],
        )
        return EvidenceSufficiencyResult.model_validate(payload)

    async def synthesize_answer(
        self,
        *,
        query: str,
        object_key: str,
        evidence: dict[str, Any],
    ) -> AnswerSynthesisResult:
        payload = await self._chat_json(
            schema_name="answer_synthesis",
            response_model=AnswerSynthesisResult,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Write a short object-location answer using only the structured "
                        "evidence. Never add a location that is not in evidence. Use "
                        "conservative language such as appears, last saw, or please verify."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "query": query,
                            "object_key": object_key,
                            "evidence": evidence,
                        },
                        default=str,
                    ),
                },
            ],
        )
        return AnswerSynthesisResult.model_validate(payload)

    async def _chat_json(
        self,
        *,
        schema_name: str,
        response_model: type[BaseModel],
        messages: list[dict[str, str]],
    ) -> dict[str, Any]:
        key = self._settings.fireworks_key_value()
        if key is None:
            raise FireworksProviderUnavailable(
                "Fireworks API key is not configured; deterministic fallback is available."
            )

        schema = response_model.model_json_schema()
        request_payload = {
            "model": self._settings.fireworks_model,
            "messages": messages,
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "schema": schema,
                },
            },
        }

        try:
            async with httpx.AsyncClient(
                base_url=str(self._settings.fireworks_base_url).rstrip("/"),
                timeout=self._settings.fireworks_timeout_seconds,
                transport=self._transport,
            ) as client:
                response = await client.post(
                    "chat/completions",
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    },
                    json=request_payload,
                )
        except httpx.HTTPError as exc:
            raise FireworksProviderError(
                f"Fireworks structured request failed: {exc.__class__.__name__}."
            ) from exc

        if response.is_error:
            raise FireworksProviderError(
                f"Fireworks structured request returned HTTP {response.status_code}."
            )

        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise FireworksProviderError("Fireworks returned an unexpected response shape.") from exc

        if isinstance(content, dict):
            return content
        if not isinstance(content, str):
            raise FireworksProviderError("Fireworks returned non-text structured content.")

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise FireworksProviderError("Fireworks returned non-JSON structured content.") from exc
        if not isinstance(parsed, dict):
            raise FireworksProviderError("Fireworks structured content was not a JSON object.")
        return parsed
