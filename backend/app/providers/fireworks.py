from __future__ import annotations

import json
from typing import Any

import httpx
from pydantic import BaseModel, Field

from app.config import Settings
from app.observability import add_trace_outputs, langsmith_trace
from app.schemas import AssistantIntent, QueryConfidence, QueryIntent, ServiceHealthState, ServiceStatus


class FireworksProviderUnavailable(RuntimeError):
    pass


class FireworksProviderError(RuntimeError):
    pass


class QueryRoutingResult(BaseModel):
    intent: QueryIntent = QueryIntent.UNKNOWN
    object_key: str | None = None
    confidence: QueryConfidence = QueryConfidence.LOW


class AssistantRoutingResult(BaseModel):
    intent: AssistantIntent = AssistantIntent.UNSUPPORTED
    confidence: QueryConfidence = QueryConfidence.LOW
    reason: str = ""


class EvidenceSufficiencyResult(BaseModel):
    sufficient: bool
    confidence: QueryConfidence = QueryConfidence.LOW
    needs_human_verification: bool = True
    reason: str = Field(default="")


class AnswerSynthesisResult(BaseModel):
    answer: str
    confidence: QueryConfidence
    needs_human_verification: bool = True


class SemanticAnswerSynthesisResult(BaseModel):
    answer: str
    confidence: QueryConfidence
    needs_human_verification: bool = True


class DailyDiarySynthesisResult(BaseModel):
    summary: str
    highlights: list[str] = Field(default_factory=list)
    needs_review: list[str] = Field(default_factory=list)


class CareNoteSynthesisResult(BaseModel):
    summary: str
    bullets: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)


class ObservationEnrichmentResult(BaseModel):
    summary: str
    label_suggestions: list[dict[str, Any]] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)
    spatial_notes: list[str] = Field(default_factory=list)


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

    async def route_assistant_query(
        self,
        *,
        query: str,
        known_object_keys: list[str],
    ) -> AssistantRoutingResult:
        payload = await self._chat_json(
            schema_name="assistant_routing",
            response_model=AssistantRoutingResult,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Classify a patient question for an assistive home-memory prototype. "
                        "Valid intents are object_location, guided_recovery, semantic_memory, "
                        "diary, family_message, hydration, wellness, setup_status, and unsupported. "
                        "Use object_location for where-is questions, guided_recovery for help finding "
                        "or recovering a known object, diary for day/activity/care-note recall, "
                        "family_message for reminders from family, hydration for drink or water check-ins, "
                        "wellness for check-in/fall/stillness review, setup_status for provider/node/status "
                        "questions, and unsupported for medical advice or unrelated requests. "
                        "Do not invent evidence or capabilities."
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
        return AssistantRoutingResult.model_validate(payload)

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

    async def enrich_observation(
        self,
        *,
        observation: dict[str, Any],
        focus: str,
    ) -> ObservationEnrichmentResult:
        payload = await self._chat_json(
            schema_name="observation_enrichment",
            response_model=ObservationEnrichmentResult,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You enrich structured live Afferens observations for an assistive "
                        "home-memory prototype. Afferens is the physical evidence source of "
                        "truth. Suggest likely label refinements, ambiguity, spatial context, "
                        "and conservative safety notes only from the provided observation. "
                        "Do not claim diagnosis, emergency response, certified fall detection, "
                        "medication advice, or facts absent from evidence."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "focus": focus,
                            "observation": observation,
                        },
                        default=str,
                    ),
                },
            ],
        )
        return ObservationEnrichmentResult.model_validate(payload)

    async def synthesize_semantic_answer(
        self,
        *,
        question: str,
        citations: list[dict[str, Any]],
    ) -> SemanticAnswerSynthesisResult:
        payload = await self._chat_json(
            schema_name="semantic_answer_synthesis",
            response_model=SemanticAnswerSynthesisResult,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Write a short, conservative memory answer for an assistive home-memory "
                        "prototype. Use only the supplied cited memory items. If citations are "
                        "insufficient, say so. Do not make medical, diagnosis, emergency, or "
                        "surveillance claims."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "question": question,
                            "citations": citations,
                        },
                        default=str,
                    ),
                },
            ],
        )
        return SemanticAnswerSynthesisResult.model_validate(payload)

    async def synthesize_daily_diary(
        self,
        *,
        diary_date: str,
        events: list[dict[str, Any]],
        deterministic: dict[str, Any],
    ) -> DailyDiarySynthesisResult:
        payload = await self._chat_json(
            schema_name="daily_diary_synthesis",
            response_model=DailyDiarySynthesisResult,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Write a conservative daily diary summary for an assistive home-memory "
                        "prototype. Use only cited structured events. Keep wording observational, "
                        "non-clinical, and evidence-backed. Do not infer hydration intake from "
                        "water, bottle, or cup visibility alone."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "date": diary_date,
                            "events": events,
                            "deterministic_fallback": deterministic,
                        },
                        default=str,
                    ),
                },
            ],
        )
        return DailyDiarySynthesisResult.model_validate(payload)

    async def synthesize_care_note(
        self,
        *,
        note_date: str,
        audience: str,
        events: list[dict[str, Any]],
        deterministic: dict[str, Any],
    ) -> CareNoteSynthesisResult:
        payload = await self._chat_json(
            schema_name="care_note_synthesis",
            response_model=CareNoteSynthesisResult,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Write a concise caregiver or care-home note for an assistive home-memory "
                        "prototype. Use only cited structured events. Use calm, low-burden, "
                        "non-clinical language and preserve human verification for important "
                        "situations. Do not claim emergency response, diagnosis, or certified "
                        "fall detection."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "date": note_date,
                            "audience": audience,
                            "events": events,
                            "deterministic_fallback": deterministic,
                        },
                        default=str,
                    ),
                },
            ],
        )
        return CareNoteSynthesisResult.model_validate(payload)

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

        trace_inputs = {
            "provider": self.provider_name,
            "schema_name": schema_name,
            "model": self._settings.fireworks_model,
            "message_count": len(messages),
            "schema_fields": sorted((schema.get("properties") or {}).keys()),
        }
        if self._settings.langsmith_trace_content:
            trace_inputs["messages"] = messages

        try:
            with langsmith_trace(
                self._settings,
                f"fireworks.{schema_name}",
                run_type="llm",
                inputs=trace_inputs,
                metadata={
                    "provider": self.provider_name,
                    "model": self._settings.fireworks_model,
                    "schema_name": schema_name,
                },
                tags=["fireworks", "structured-output", schema_name],
            ) as trace_run:
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
            add_trace_outputs(
                trace_run,
                {
                    "provider": self.provider_name,
                    "schema_name": schema_name,
                    "parsed_keys": sorted(content.keys()),
                    "usage": payload.get("usage"),
                    "content": content if self._settings.langsmith_trace_content else None,
                },
                include_content=self._settings.langsmith_trace_content,
            )
            return content
        if not isinstance(content, str):
            raise FireworksProviderError("Fireworks returned non-text structured content.")

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise FireworksProviderError("Fireworks returned non-JSON structured content.") from exc
        if not isinstance(parsed, dict):
            raise FireworksProviderError("Fireworks structured content was not a JSON object.")
        add_trace_outputs(
            trace_run,
            {
                "provider": self.provider_name,
                "schema_name": schema_name,
                "parsed_keys": sorted(parsed.keys()),
                "usage": payload.get("usage"),
                "content": parsed if self._settings.langsmith_trace_content else None,
            },
            include_content=self._settings.langsmith_trace_content,
        )
        return parsed
