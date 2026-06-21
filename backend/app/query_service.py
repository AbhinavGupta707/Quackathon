from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.ids import new_id
from app.object_search import (
    infer_object_key_from_query,
    looks_like_object_location_query,
    normalize_object_key,
    object_candidates,
)
from app.providers.fireworks import (
    AnswerSynthesisResult,
    EvidenceSufficiencyResult,
    FireworksProviderError,
    FireworksProviderUnavailable,
    FireworksReasoningAdapter,
    QueryRoutingResult,
)
from app.schemas import (
    DetectedObject,
    LastSeenObject,
    Observation,
    QueryConfidence,
    QueryIntent,
    QueryLog,
    QueryRequest,
    QueryResponse,
    Task,
    TaskState,
    TaskType,
    utc_now,
)
from app.services import DataSpineService
from app.workflows.object_recovery import ObjectRecoveryWorkflow


@dataclass
class EvidenceSelection:
    object_key: str | None
    current_object: DetectedObject | None
    memory: LastSeenObject | None
    evidence_observation_ids: list[str]

    @property
    def has_current_evidence(self) -> bool:
        return self.current_object is not None

    @property
    def has_memory_evidence(self) -> bool:
        return self.memory is not None


class QueryAnswerService:
    def __init__(
        self,
        data_spine: DataSpineService,
        *,
        reasoning: FireworksReasoningAdapter,
        workflow: ObjectRecoveryWorkflow,
    ) -> None:
        self._data_spine = data_spine
        self._reasoning = reasoning
        self._workflow = workflow

    async def answer(self, request: QueryRequest) -> QueryResponse:
        latest_observation = self._data_spine.latest_observation()
        memories = self._data_spine.list_last_seen_objects()
        latest_objects = latest_observation.objects if latest_observation else []
        candidates = object_candidates(memories=memories, observation_objects=latest_objects)

        known_object_keys = [candidate.object_key for candidate in candidates]
        route = await self._route_query(request.query, known_object_keys)
        deterministic_object_key = infer_object_key_from_query(request.query, candidates)
        provider_object_key = normalize_object_key(route.object_key) if route.object_key else None
        if provider_object_key not in set(known_object_keys):
            provider_object_key = None
        object_key = provider_object_key or deterministic_object_key
        intent = self._intent(route, request.query, object_key)

        if intent != QueryIntent.OBJECT_LOCATION:
            response = QueryResponse(
                answer=(
                    "I can only answer evidence-backed object-location questions right now. "
                    "Please verify important situations in person."
                ),
                confidence=QueryConfidence.LOW,
                intent=intent,
                used_current_perception=False,
                used_memory=False,
                needs_human_verification=True,
                evidence_observation_ids=[],
            )
            self._record_query(request, response, provider=None)
            return response

        selection = self._select_evidence(
            object_key=object_key,
            latest_observation=latest_observation,
            memories=memories,
        )

        if selection.object_key is None:
            response = QueryResponse(
                answer=(
                    "I do not have observation evidence for that object yet. "
                    "Start a live Afferens sync after the object is visible, then ask again."
                ),
                confidence=QueryConfidence.LOW,
                intent=QueryIntent.OBJECT_LOCATION,
                used_current_perception=False,
                used_memory=False,
                needs_human_verification=True,
                evidence_observation_ids=[],
            )
            self._record_query(request, response, provider=None)
            return response

        evidence_bundle = self._evidence_bundle(selection, latest_observation)
        assessment = await self._assess_evidence(request.query, selection.object_key, evidence_bundle)

        if selection.current_object is not None:
            response = await self._answer_from_current_evidence(
                request=request,
                selection=selection,
                evidence_bundle=evidence_bundle,
                assessment=assessment,
            )
            self._record_query(request, response, provider=self._provider_name(assessment))
            return response

        if selection.memory is not None:
            response = await self._answer_from_memory(
                request=request,
                selection=selection,
                evidence_bundle=evidence_bundle,
                assessment=assessment,
            )
            self._record_query(request, response, provider=self._provider_name(assessment))
            return response

        response = QueryResponse(
            answer=(
                f"I do not have enough live observation evidence to locate {selection.object_key}. "
                "Please verify in person or sync after the object is visible."
            ),
            confidence=QueryConfidence.LOW,
            intent=QueryIntent.OBJECT_LOCATION,
            used_current_perception=False,
            used_memory=False,
            needs_human_verification=True,
            evidence_observation_ids=[],
        )
        self._record_query(request, response, provider=None)
        return response

    async def _route_query(
        self,
        query: str,
        known_object_keys: list[str],
    ) -> QueryRoutingResult:
        try:
            return await self._reasoning.route_query(
                query=query,
                known_object_keys=known_object_keys,
            )
        except (FireworksProviderUnavailable, FireworksProviderError, ValueError):
            return QueryRoutingResult(
                intent=QueryIntent.OBJECT_LOCATION
                if looks_like_object_location_query(query)
                else QueryIntent.UNKNOWN,
                object_key=None,
                confidence=QueryConfidence.LOW,
            )

    async def _assess_evidence(
        self,
        query: str,
        object_key: str,
        evidence_bundle: dict[str, Any],
    ) -> EvidenceSufficiencyResult | None:
        if not evidence_bundle.get("evidence_observation_ids"):
            return None
        try:
            return await self._reasoning.assess_evidence(
                query=query,
                object_key=object_key,
                evidence=evidence_bundle,
            )
        except (FireworksProviderUnavailable, FireworksProviderError, ValueError):
            return None

    async def _answer_from_current_evidence(
        self,
        *,
        request: QueryRequest,
        selection: EvidenceSelection,
        evidence_bundle: dict[str, Any],
        assessment: EvidenceSufficiencyResult | None,
    ) -> QueryResponse:
        detected = selection.current_object
        assert detected is not None

        confidence = self._confidence_from_score(detected.confidence, current=True)
        answer = self._current_answer(detected, evidence_bundle)
        synthesized = await self._synthesize_if_safe(
            request.query,
            selection.object_key or detected.object_key,
            evidence_bundle,
            assessment,
        )
        if synthesized is not None:
            answer = synthesized.answer
            confidence = self._min_confidence(confidence, synthesized.confidence)

        return QueryResponse(
            answer=answer,
            confidence=confidence,
            intent=QueryIntent.OBJECT_LOCATION,
            used_current_perception=True,
            used_memory=False,
            needs_human_verification=True,
            evidence_observation_ids=selection.evidence_observation_ids,
        )

    async def _answer_from_memory(
        self,
        *,
        request: QueryRequest,
        selection: EvidenceSelection,
        evidence_bundle: dict[str, Any],
        assessment: EvidenceSufficiencyResult | None,
    ) -> QueryResponse:
        memory = selection.memory
        assert memory is not None

        workflow_state = self._workflow.plan_recovery(
            query=request.query,
            object_key=memory.object_key,
            memory=memory,
            current_visible=False,
        )
        task = self._get_or_create_recovery_task(
            request=request,
            memory=memory,
            recommended_action=workflow_state.get("recommended_action"),
        )

        confidence = self._memory_confidence(memory.last_confidence)
        answer = self._memory_answer(memory)
        synthesized = await self._synthesize_if_safe(
            request.query,
            memory.object_key,
            evidence_bundle,
            assessment,
            max_confidence=QueryConfidence.MEDIUM,
        )
        if synthesized is not None:
            answer = synthesized.answer
            confidence = self._min_confidence(confidence, synthesized.confidence)

        return QueryResponse(
            answer=answer,
            confidence=confidence,
            intent=QueryIntent.OBJECT_LOCATION,
            used_current_perception=False,
            used_memory=True,
            needs_human_verification=True,
            evidence_observation_ids=selection.evidence_observation_ids,
            task_id=task.id,
        )

    async def _synthesize_if_safe(
        self,
        query: str,
        object_key: str,
        evidence_bundle: dict[str, Any],
        assessment: EvidenceSufficiencyResult | None,
        *,
        max_confidence: QueryConfidence | None = None,
    ) -> AnswerSynthesisResult | None:
        if assessment is not None and not assessment.sufficient:
            return None
        if not evidence_bundle.get("evidence_observation_ids"):
            return None
        try:
            synthesized = await self._reasoning.synthesize_answer(
                query=query,
                object_key=object_key,
                evidence=evidence_bundle,
            )
        except (FireworksProviderUnavailable, FireworksProviderError, ValueError):
            return None
        if not synthesized.answer.strip():
            return None
        if max_confidence is not None:
            synthesized.confidence = self._min_confidence(max_confidence, synthesized.confidence)
        return synthesized

    def _select_evidence(
        self,
        *,
        object_key: str | None,
        latest_observation: Observation | None,
        memories: list[LastSeenObject],
    ) -> EvidenceSelection:
        memory_by_key = {memory.object_key: memory for memory in memories}
        current_object: DetectedObject | None = None
        resolved_key = object_key

        if latest_observation is not None and object_key is not None:
            for detected in latest_observation.objects:
                if detected.object_key == object_key and self._is_confidently_visible(detected):
                    current_object = detected
                    resolved_key = detected.object_key
                    break

        if resolved_key is None:
            return EvidenceSelection(
                object_key=None,
                current_object=None,
                memory=None,
                evidence_observation_ids=[],
            )

        memory = memory_by_key.get(resolved_key)
        evidence_ids: list[str] = []
        if current_object is not None and latest_observation is not None:
            evidence_ids.append(latest_observation.id)
        elif memory is not None:
            evidence_ids.extend(memory.evidence_observation_ids or [memory.last_seen_observation_id])

        return EvidenceSelection(
            object_key=resolved_key,
            current_object=current_object,
            memory=memory,
            evidence_observation_ids=list(dict.fromkeys(evidence_ids)),
        )

    def _get_or_create_recovery_task(
        self,
        *,
        request: QueryRequest,
        memory: LastSeenObject,
        recommended_action: str | None,
    ) -> Task:
        existing = self._data_spine.find_open_object_recovery_task(memory.object_key)
        if existing is not None:
            return existing

        evidence_ids = list(dict.fromkeys(memory.evidence_observation_ids or [memory.last_seen_observation_id]))
        task = Task(
            id=new_id("task"),
            type=TaskType.OBJECT_RECOVERY,
            state=TaskState.OPEN,
            title=f"Find {memory.display_name}",
            body=self._memory_answer(memory),
            recommended_action=recommended_action or self._recommended_action(memory),
            evidence_observation_ids=evidence_ids,
            metadata={
                "object_key": memory.object_key,
                "display_name": memory.display_name,
                "last_seen_observation_id": memory.last_seen_observation_id,
                "opened_from_query": request.query,
                "session_id": request.session_id,
            },
        )
        task = self._data_spine.create_task(task)
        self._data_spine.add_task_event(
            task_id=task.id,
            event_type="object_recovery_opened",
            message=f"Opened object recovery for {memory.object_key} from an evidence-backed query.",
            evidence_observation_ids=evidence_ids,
        )
        return task

    def _record_query(
        self,
        request: QueryRequest,
        response: QueryResponse,
        *,
        provider: str | None,
    ) -> None:
        self._data_spine.create_query(
            QueryLog(
                id=new_id("query"),
                query_text=request.query,
                session_id=request.session_id,
                intent=response.intent,
                answer=response.answer,
                confidence=response.confidence,
                evidence_observation_ids=response.evidence_observation_ids,
                task_id=response.task_id,
                provider=provider,
            )
        )

    @staticmethod
    def _intent(route: QueryRoutingResult, query: str, object_key: str | None) -> QueryIntent:
        if route.intent == QueryIntent.OBJECT_LOCATION or object_key is not None:
            return QueryIntent.OBJECT_LOCATION
        if looks_like_object_location_query(query):
            return QueryIntent.OBJECT_LOCATION
        return route.intent

    @staticmethod
    def _is_confidently_visible(detected: DetectedObject) -> bool:
        return detected.confidence is None or detected.confidence >= 0.5

    @staticmethod
    def _confidence_from_score(score: float | None, *, current: bool) -> QueryConfidence:
        if score is None:
            return QueryConfidence.MEDIUM if current else QueryConfidence.LOW
        if current and score >= 0.75:
            return QueryConfidence.HIGH
        if score >= 0.4:
            return QueryConfidence.MEDIUM
        return QueryConfidence.LOW

    def _memory_confidence(self, score: float | None) -> QueryConfidence:
        confidence = self._confidence_from_score(score, current=False)
        return self._min_confidence(QueryConfidence.MEDIUM, confidence)

    @staticmethod
    def _min_confidence(
        left: QueryConfidence,
        right: QueryConfidence,
    ) -> QueryConfidence:
        rank = {
            QueryConfidence.LOW: 0,
            QueryConfidence.MEDIUM: 1,
            QueryConfidence.HIGH: 2,
        }
        return left if rank[left] <= rank[right] else right

    @staticmethod
    def _current_answer(detected: DetectedObject, evidence: dict[str, Any]) -> str:
        location = detected.relative_location
        timestamp = evidence.get("current_observation", {}).get("timestamp_utc")
        when = f" in the latest live observation at {timestamp}" if timestamp else " in the latest live observation"
        if location:
            return f"{detected.display_name} appears visible{when}, near {location}. Please verify in person."
        return f"{detected.display_name} appears visible{when}. Please verify in person."

    @staticmethod
    def _memory_answer(memory: LastSeenObject) -> str:
        when = QueryAnswerService._format_when(memory.last_seen_at)
        location = memory.last_seen_relative_location
        if location:
            return (
                f"I last saw {memory.display_name} in {memory.last_seen_room} near {location} "
                f"at {when}. Please verify in person."
            )
        return (
            f"I last saw {memory.display_name} in {memory.last_seen_room} at {when}. "
            "Please verify in person."
        )

    @staticmethod
    def _recommended_action(memory: LastSeenObject) -> str:
        if memory.last_seen_relative_location:
            return (
                f"Check {memory.last_seen_room} near {memory.last_seen_relative_location}, "
                "then place the object in view for live verification."
            )
        return (
            f"Check {memory.last_seen_room}, then place the object in view for live verification."
        )

    @staticmethod
    def _format_when(value: datetime) -> str:
        return value.isoformat().replace("+00:00", "Z")

    @staticmethod
    def _evidence_bundle(
        selection: EvidenceSelection,
        latest_observation: Observation | None,
    ) -> dict[str, Any]:
        bundle: dict[str, Any] = {
            "object_key": selection.object_key,
            "evidence_observation_ids": selection.evidence_observation_ids,
        }
        if selection.current_object is not None and latest_observation is not None:
            bundle["current_observation"] = {
                "id": latest_observation.id,
                "timestamp_utc": latest_observation.timestamp_utc.isoformat(),
                "room_id": latest_observation.room_id,
                "scene_summary": latest_observation.scene_summary,
                "object": selection.current_object.model_dump(mode="json"),
            }
        if selection.memory is not None:
            bundle["last_seen_memory"] = selection.memory.model_dump(mode="json")
        return bundle

    @staticmethod
    def _provider_name(assessment: EvidenceSufficiencyResult | None) -> str | None:
        return "fireworks" if assessment is not None else None
