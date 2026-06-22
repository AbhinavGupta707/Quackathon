from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from app.afferens_adapter import AfferensAdapter
from app.config import Settings
from app.db import get_database_status
from app.diary import DailyCareService
from app.object_search import looks_like_object_location_query, object_candidates
from app.providers.fireworks import (
    FireworksProviderError,
    FireworksProviderUnavailable,
    FireworksReasoningAdapter,
)
from app.query_service import QueryAnswerService
from app.schemas import (
    AfferensConnectionState,
    AssistantAskRequest,
    AssistantAskResponse,
    AssistantIntent,
    CareNoteAudience,
    CareNote,
    DailyDiaryEntry,
    HydrationStatus,
    QueryConfidence,
    QueryRequest,
    SemanticMemoryAskRequest,
    SemanticMemorySourceType,
    ServiceHealthState,
    utc_now,
)
from app.semantic_memory import SemanticMemoryService
from app.services import DataSpineService
from app.wellness import HydrationWellnessService


@dataclass(frozen=True)
class AssistantRoute:
    intent: AssistantIntent
    provider: str
    confidence: QueryConfidence
    reason: str = ""


class AssistantService:
    def __init__(
        self,
        data_spine: DataSpineService,
        *,
        query_service: QueryAnswerService,
        semantic_memory: SemanticMemoryService,
        daily_care: DailyCareService,
        wellness: HydrationWellnessService,
        fireworks: FireworksReasoningAdapter,
        afferens: AfferensAdapter,
        settings: Settings,
    ) -> None:
        self._data_spine = data_spine
        self._query_service = query_service
        self._semantic_memory = semantic_memory
        self._daily_care = daily_care
        self._wellness = wellness
        self._fireworks = fireworks
        self._afferens = afferens
        self._settings = settings

    async def ask(self, request: AssistantAskRequest) -> AssistantAskResponse:
        route = await self._route(request.query)
        if self._is_medical_advice_request(request.query):
            route = AssistantRoute(
                intent=AssistantIntent.UNSUPPORTED,
                provider="deterministic",
                confidence=QueryConfidence.LOW,
                reason="medical_or_emergency_advice",
            )

        if route.intent in {AssistantIntent.OBJECT_LOCATION, AssistantIntent.GUIDED_RECOVERY}:
            return await self._answer_object_or_recovery(request, route)
        if route.intent == AssistantIntent.SEMANTIC_MEMORY:
            return await self._answer_semantic_memory(request, route)
        if route.intent == AssistantIntent.DIARY:
            return self._answer_diary_or_care_note(request, route)
        if route.intent == AssistantIntent.FAMILY_MESSAGE:
            return self._answer_family_message(route)
        if route.intent == AssistantIntent.HYDRATION:
            return self._answer_hydration(route)
        if route.intent == AssistantIntent.WELLNESS:
            return self._answer_wellness(route)
        if route.intent == AssistantIntent.SETUP_STATUS:
            return await self._answer_setup_status(route)
        return self._answer_unsupported(route)

    async def _route(self, query: str) -> AssistantRoute:
        known_object_keys = self._known_object_keys()
        deterministic = self._deterministic_route(query, known_object_keys)
        if deterministic.intent in {AssistantIntent.OBJECT_LOCATION, AssistantIntent.GUIDED_RECOVERY}:
            return AssistantRoute(
                intent=deterministic.intent,
                provider=deterministic.provider,
                confidence=deterministic.confidence,
                reason="deterministic_object_query_fast_path",
            )

        try:
            routed = await self._fireworks.route_assistant_query(
                query=query,
                known_object_keys=known_object_keys,
            )
            return AssistantRoute(
                intent=routed.intent,
                provider="fireworks",
                confidence=routed.confidence,
                reason=routed.reason,
            )
        except (FireworksProviderUnavailable, FireworksProviderError, ValueError):
            return deterministic

    def _deterministic_route(
        self,
        query: str,
        known_object_keys: list[str],
    ) -> AssistantRoute:
        normalized = _normalize(query)
        words = set(_tokens(normalized))

        if self._is_setup_query(normalized, words):
            intent = AssistantIntent.SETUP_STATUS
        elif looks_like_object_location_query(query) and not self._looks_like_hydration_advice(words):
            intent = (
                AssistantIntent.GUIDED_RECOVERY
                if words & {"find", "help", "locate", "recover", "search"}
                else AssistantIntent.OBJECT_LOCATION
            )
        elif words & {"reminder", "reminders", "message", "messages", "family"} or (
            {"supposed", "remember"} <= words
        ):
            intent = AssistantIntent.FAMILY_MESSAGE
        elif words & {"hydration", "hydrate", "drink", "drank", "water", "sip", "thirsty"}:
            intent = AssistantIntent.HYDRATION
        elif words & {"wellness", "checkin", "check", "fall", "fallen", "stillness", "okay", "alright"}:
            intent = AssistantIntent.WELLNESS
        elif (
            words & {"diary", "today", "yesterday", "morning", "evening", "activity", "activities"}
            or "care note" in normalized
            or "care notes" in normalized
            or "care home" in normalized
        ):
            intent = AssistantIntent.DIARY
        elif words & {"memory", "remember", "recall", "visited", "visitor", "happened", "know"}:
            intent = AssistantIntent.SEMANTIC_MEMORY
        elif known_object_keys and any(key in normalized for key in known_object_keys):
            intent = AssistantIntent.SEMANTIC_MEMORY
        else:
            intent = AssistantIntent.UNSUPPORTED

        return AssistantRoute(
            intent=intent,
            provider="deterministic",
            confidence=QueryConfidence.MEDIUM if intent != AssistantIntent.UNSUPPORTED else QueryConfidence.LOW,
            reason="deterministic_keyword_route",
        )

    async def _answer_object_or_recovery(
        self,
        request: AssistantAskRequest,
        route: AssistantRoute,
    ) -> AssistantAskResponse:
        query_response = await self._query_service.answer(
            QueryRequest(query=request.query, session_id=request.session_id)
        )
        task_next_step = (
            "Follow the recovery task, then put the item back in view so live perception can verify it."
            if query_response.task_id
            else "Check the cited location and verify it in person."
        )
        if not query_response.evidence_observation_ids:
            task_next_step = "Start or check the live Afferens Node, sync current perception, then ask again."

        evidence_ids = self._unique(query_response.evidence_observation_ids)
        return AssistantAskResponse(
            intent=route.intent,
            answer=query_response.answer,
            next_step=task_next_step,
            confidence=query_response.confidence,
            provider=self._provider_for_response(route.provider),
            used_current_perception=query_response.used_current_perception,
            used_memory=query_response.used_memory,
            needs_human_verification=query_response.needs_human_verification,
            evidence_ids=evidence_ids,
            source_ids=evidence_ids,
            task_id=query_response.task_id,
            route_metadata={
                "routed_to": "query_answer_service",
                "query_intent": query_response.intent.value,
                "route_reason": route.reason,
            },
        )

    async def _answer_semantic_memory(
        self,
        request: AssistantAskRequest,
        route: AssistantRoute,
        *,
        source_types: list[SemanticMemorySourceType] | None = None,
    ) -> AssistantAskResponse:
        memory_response = await self._semantic_memory.ask(
            SemanticMemoryAskRequest(
                question=request.query,
                source_types=source_types,
            )
        )
        provider = self._provider_for_response(memory_response.provider)
        if route.provider == "fireworks":
            provider = "fireworks"
        next_step = (
            "Ask a caregiver to confirm important details."
            if memory_response.used_memory
            else "Add live evidence or a caregiver note first, then reindex memory."
        )
        return AssistantAskResponse(
            intent=route.intent,
            answer=memory_response.answer,
            next_step=next_step,
            confidence=memory_response.confidence,
            provider=provider,
            used_current_perception=False,
            used_memory=memory_response.used_memory,
            needs_human_verification=memory_response.needs_human_verification,
            evidence_ids=self._unique(memory_response.evidence_ids),
            source_ids=self._unique(memory_response.source_ids),
            route_metadata={
                "routed_to": "semantic_memory",
                "citation_count": len(memory_response.citations),
                "route_reason": route.reason,
            },
        )

    def _answer_diary_or_care_note(
        self,
        request: AssistantAskRequest,
        route: AssistantRoute,
    ) -> AssistantAskResponse:
        target_date = self._date_from_query(request.query)
        normalized = _normalize(request.query)
        if "care note" in normalized or "care notes" in normalized or "care home" in normalized:
            notes = self._daily_care.list_care_notes(target_date)
            if not notes:
                notes = [self._daily_care.generate_care_note(target_date, audience=CareNoteAudience.FAMILY)]
            return self._response_from_care_notes(notes, target_date, route)

        diary = self._daily_care.get_diary(target_date) or self._daily_care.generate_diary(target_date)
        return self._response_from_diary(diary, route)

    def _response_from_diary(
        self,
        diary: DailyDiaryEntry,
        route: AssistantRoute,
    ) -> AssistantAskResponse:
        has_evidence = bool(diary.evidence_ids)
        answer = diary.summary if has_evidence else (
            f"I do not have evidence-backed diary activity for {diary.date.isoformat()} yet."
        )
        if has_evidence and diary.needs_review:
            answer = f"{answer} {diary.needs_review[0]}"
        return AssistantAskResponse(
            intent=AssistantIntent.DIARY,
            answer=answer,
            next_step=(
                "Ask a caregiver to verify the details that matter."
                if has_evidence
                else "Let live Afferens evidence or caregiver notes accumulate, then ask again."
            ),
            confidence=QueryConfidence.MEDIUM if has_evidence else QueryConfidence.LOW,
            provider=self._provider_for_response(route.provider),
            used_current_perception=False,
            used_memory=has_evidence,
            needs_human_verification=True,
            evidence_ids=self._unique(diary.evidence_ids),
            source_ids=[diary.id] if has_evidence else [],
            route_metadata={"routed_to": "daily_diary", "route_reason": route.reason},
        )

    def _response_from_care_notes(
        self,
        notes: list[CareNote],
        target_date: date,
        route: AssistantRoute,
    ) -> AssistantAskResponse:
        cited = [note for note in notes if note.evidence_ids]
        if not cited:
            return AssistantAskResponse(
                intent=AssistantIntent.DIARY,
                answer=f"I do not have evidence-backed care notes for {target_date.isoformat()} yet.",
                next_step="Create a caregiver note from live evidence or check in person.",
                confidence=QueryConfidence.LOW,
                provider=self._provider_for_response(route.provider),
                used_current_perception=False,
                used_memory=False,
                needs_human_verification=True,
                route_metadata={"routed_to": "care_notes", "route_reason": route.reason},
            )

        note = cited[0]
        evidence_ids = self._unique([evidence_id for item in cited for evidence_id in item.evidence_ids])
        answer = note.summary
        if note.follow_ups:
            answer = f"{answer} {note.follow_ups[0]}"
        return AssistantAskResponse(
            intent=AssistantIntent.DIARY,
            answer=answer,
            next_step="Ask a caregiver to confirm before acting on the note.",
            confidence=QueryConfidence.MEDIUM,
            provider=self._provider_for_response(route.provider),
            used_current_perception=False,
            used_memory=True,
            needs_human_verification=True,
            evidence_ids=evidence_ids,
            source_ids=[item.id for item in cited],
            route_metadata={"routed_to": "care_notes", "route_reason": route.reason},
        )

    def _answer_family_message(self, route: AssistantRoute) -> AssistantAskResponse:
        messages = self._daily_care.active_family_messages()
        if not messages:
            return AssistantAskResponse(
                intent=AssistantIntent.FAMILY_MESSAGE,
                answer="I do not have an active family message or reminder for you right now.",
                next_step="Ask a caregiver or family member if you expected a reminder.",
                confidence=QueryConfidence.LOW,
                provider=self._provider_for_response(route.provider),
                used_current_perception=False,
                used_memory=False,
                needs_human_verification=True,
                route_metadata={"routed_to": "family_messages", "route_reason": route.reason},
            )

        top_messages = messages[:2]
        answer = " ".join(f"{message.title}: {message.body}" for message in top_messages)
        if len(messages) > len(top_messages):
            answer += f" There are {len(messages) - len(top_messages)} more active prompt(s)."
        return AssistantAskResponse(
            intent=AssistantIntent.FAMILY_MESSAGE,
            answer=f"{answer} Please verify important details with a person.",
            next_step="Review or acknowledge the family prompt when it has been handled.",
            confidence=QueryConfidence.MEDIUM,
            provider=self._provider_for_response(route.provider),
            used_current_perception=False,
            used_memory=True,
            needs_human_verification=True,
            source_ids=[message.id for message in top_messages],
            route_metadata={"routed_to": "family_messages", "route_reason": route.reason},
        )

    def _answer_hydration(self, route: AssistantRoute) -> AssistantAskResponse:
        today = utc_now().date()
        summary = self._wellness.hydration_summary(today)
        source_ids = [event.id for event in summary.events]
        has_evidence = bool(summary.evidence_ids or source_ids)
        if summary.status == HydrationStatus.OKAY:
            next_step = "Keep using caregiver-confirmed or action-backed hydration records."
        elif has_evidence:
            next_step = "Consider a gentle check-in; object visibility alone does not count as drinking."
        else:
            next_step = "Use in-person context if hydration matters."
        return AssistantAskResponse(
            intent=AssistantIntent.HYDRATION,
            answer=summary.message,
            next_step=next_step,
            confidence=QueryConfidence.MEDIUM if summary.status == HydrationStatus.OKAY else QueryConfidence.LOW,
            provider=self._provider_for_response(route.provider),
            used_current_perception=bool(summary.evidence_ids),
            used_memory=has_evidence,
            needs_human_verification=True,
            evidence_ids=self._unique(summary.evidence_ids),
            source_ids=self._unique(source_ids),
            route_metadata={
                "routed_to": "hydration_summary",
                "hydration_status": summary.status.value,
                "route_reason": route.reason,
            },
        )

    def _answer_wellness(self, route: AssistantRoute) -> AssistantAskResponse:
        today = utc_now().date()
        checks = self._wellness.generate_wellness_checks(today)
        cited = [check for check in checks if check.evidence_ids]
        if not cited:
            return AssistantAskResponse(
                intent=AssistantIntent.WELLNESS,
                answer="I do not have live wellness evidence or an evidence-backed wellness check for today.",
                next_step="If you are worried, please check in with a caregiver or trusted person.",
                confidence=QueryConfidence.LOW,
                provider=self._provider_for_response(route.provider),
                used_current_perception=False,
                used_memory=False,
                needs_human_verification=True,
                route_metadata={"routed_to": "wellness_checks", "route_reason": route.reason},
            )

        check = cited[0]
        evidence_ids = self._unique([evidence_id for item in cited for evidence_id in item.evidence_ids])
        return AssistantAskResponse(
            intent=AssistantIntent.WELLNESS,
            answer=f"{check.title}: {check.body}",
            next_step="Please check in and verify the situation in person.",
            confidence=check.confidence,
            provider=self._provider_for_response(route.provider),
            used_current_perception=True,
            used_memory=True,
            needs_human_verification=True,
            evidence_ids=evidence_ids,
            source_ids=[item.id for item in cited],
            route_metadata={"routed_to": "wellness_checks", "route_reason": route.reason},
        )

    async def _answer_setup_status(self, route: AssistantRoute) -> AssistantAskResponse:
        afferens_status = await self._afferens.fetch_latest()
        fireworks_status = self._fireworks.status()
        database_status = get_database_status(self._settings)

        parts = [
            f"Afferens status: {afferens_status.status.message}",
            f"Fireworks status: {fireworks_status.message}",
            f"Database status: {database_status.message}",
        ]
        if afferens_status.status.state == AfferensConnectionState.MISSING_KEY:
            next_step = "Add the Afferens API key, then set up a live node at https://afferens.com/node."
        elif afferens_status.status.state == AfferensConnectionState.NO_LIVE_EVENTS:
            next_step = "Open https://afferens.com/node and start a live Vision node before debugging runtime logic."
        elif afferens_status.status.state == AfferensConnectionState.LIVE:
            next_step = "Live Vision is available; ask an evidence-backed question."
        else:
            next_step = "Follow the Afferens activation flow before checking camera permissions or downstream logic."

        confidence = QueryConfidence.MEDIUM
        if (
            afferens_status.status.state == AfferensConnectionState.ERROR
            or database_status.state == ServiceHealthState.ERROR
        ):
            confidence = QueryConfidence.LOW

        return AssistantAskResponse(
            intent=AssistantIntent.SETUP_STATUS,
            answer=" ".join(parts),
            next_step=next_step,
            confidence=confidence,
            provider=self._provider_for_response(route.provider),
            used_current_perception=afferens_status.status.state == AfferensConnectionState.LIVE,
            used_memory=False,
            needs_human_verification=True,
            route_metadata={
                "routed_to": "setup_status",
                "afferens_state": afferens_status.status.state.value,
                "fireworks_state": fireworks_status.state.value,
                "database_state": database_status.state.value,
                "route_reason": route.reason,
            },
        )

    def _answer_unsupported(self, route: AssistantRoute) -> AssistantAskResponse:
        return AssistantAskResponse(
            intent=AssistantIntent.UNSUPPORTED,
            answer=(
                "I can help with evidence-backed object finding, memories, diary or care-note recall, "
                "family reminders, hydration or wellness check-ins, and setup status. I cannot provide "
                "medical advice or answer without supporting records."
            ),
            next_step="Try asking about an object, a cited memory, a family reminder, hydration, wellness, or setup status.",
            confidence=QueryConfidence.LOW,
            provider=self._provider_for_response(route.provider),
            used_current_perception=False,
            used_memory=False,
            needs_human_verification=True,
            route_metadata={"routed_to": "unsupported", "route_reason": route.reason},
        )

    def _known_object_keys(self) -> list[str]:
        latest = self._data_spine.latest_observation()
        candidates = object_candidates(
            memories=self._data_spine.list_last_seen_objects(),
            observation_objects=latest.objects if latest else [],
        )
        return [candidate.object_key for candidate in candidates]

    @staticmethod
    def _date_from_query(query: str) -> date:
        normalized = _normalize(query)
        today = utc_now().date()
        if "yesterday" in normalized:
            return today - timedelta(days=1)
        return today

    @staticmethod
    def _provider_for_response(provider: str) -> str:
        if provider in {"fireworks", "hybrid_local_vector"}:
            return provider
        return "deterministic"

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        return list(dict.fromkeys(value for value in values if value))

    @staticmethod
    def _looks_like_hydration_advice(words: set[str]) -> bool:
        return bool(words & {"drink", "hydration", "hydrate", "thirsty"})

    @staticmethod
    def _is_setup_query(normalized: str, words: set[str]) -> bool:
        return bool(
            words & {"setup", "status", "configured", "provider", "providers", "node", "afferens", "fireworks"}
            or "not working" in normalized
            or "is live" in normalized
            or "live node" in normalized
        )

    @staticmethod
    def _is_medical_advice_request(query: str) -> bool:
        normalized = _normalize(query)
        return bool(
            {"diagnose", "diagnosis", "dose", "dosage", "prescribe"} & set(_tokens(normalized))
            or "medical advice" in normalized
            or "call emergency" in normalized
        )


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower().replace("-", " "))


def _tokens(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.lower())
