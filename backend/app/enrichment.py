from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.config import Settings
from app.ids import new_id
from app.providers.fireworks import (
    FireworksProviderError,
    FireworksProviderUnavailable,
    FireworksReasoningAdapter,
)
from app.schemas import (
    EnrichmentFocus,
    EnrichmentLabelSuggestion,
    EnrichmentLatestRequest,
    EnrichmentLatestResponse,
    EnrichmentProvider,
    EnrichmentProviderState,
    ModelRun,
    ModelRunState,
    Observation,
    ObservationEnrichment,
    utc_now,
)
from app.services import DataSpineService


@dataclass(frozen=True)
class EnrichmentDraft:
    provider: str
    model: str
    summary: str
    label_suggestions: list[EnrichmentLabelSuggestion]
    safety_notes: list[str]
    spatial_notes: list[str]


class ObservationEnrichmentProvider(Protocol):
    provider_name: str
    model_name: str

    async def enrich(self, observation: Observation, *, focus: EnrichmentFocus) -> EnrichmentDraft: ...


class DeterministicObservationEnrichmentProvider:
    provider_name = "deterministic"
    model_name = "deterministic-afferens-derived-v1"

    _ambiguous_labels: dict[str, str] = {
        "tv": "computer monitor or TV-like display",
        "monitor": "computer monitor or TV-like display",
        "screen": "computer monitor or TV-like display",
        "speaker": "speaker or small desk device",
        "mouse": "computer mouse or small desk device",
        "remote": "remote control or small handheld device",
        "cell phone": "phone or small rectangular device",
        "bottle": "bottle; human verification may be needed for contents",
    }

    async def enrich(self, observation: Observation, *, focus: EnrichmentFocus) -> EnrichmentDraft:
        label_suggestions: list[EnrichmentLabelSuggestion] = []
        safety_notes: list[str] = []
        spatial_notes: list[str] = []

        for detected in observation.objects:
            label = detected.label.strip().lower()
            suggested = self._ambiguous_labels.get(label)
            low_confidence = detected.confidence is not None and detected.confidence < 0.65

            if suggested is not None:
                label_suggestions.append(
                    EnrichmentLabelSuggestion(
                        object_key=detected.object_key,
                        afferens_label=detected.label,
                        suggested_label=suggested,
                        confidence=detected.confidence,
                        reason="Afferens label can be visually ambiguous in a home scene.",
                    )
                )
            elif low_confidence:
                label_suggestions.append(
                    EnrichmentLabelSuggestion(
                        object_key=detected.object_key,
                        afferens_label=detected.label,
                        suggested_label=detected.display_name,
                        confidence=detected.confidence,
                        reason="Afferens confidence is low, so human verification may be needed.",
                    )
                )

            if detected.relative_location:
                spatial_notes.append(
                    f"{detected.display_name} appears {detected.relative_location}."
                )

            if label in {"medicine", "pill", "pills", "bottle"}:
                safety_notes.append(
                    f"{detected.display_name} may need checking if it is medication or should be stored safely."
                )
            if label in {"knife", "scissors"}:
                safety_notes.append(
                    f"{detected.display_name} appears visible; verify in person if it should be secured."
                )
            if label in {"stove", "oven", "microwave"}:
                safety_notes.append(
                    f"{detected.display_name} appears in the scene; verify in person if it is active or unattended."
                )

        for risk in observation.risk_signals:
            safety_notes.append(f"Afferens-derived risk signal '{risk}' may need human verification.")

        if observation.human_presence.value == "visible":
            safety_notes.append("A person appears visible; avoid autonomous safety conclusions.")

        if not label_suggestions:
            label_suggestions.append(
                EnrichmentLabelSuggestion(
                    object_key="scene",
                    afferens_label=observation.classification or "afferens_scene",
                    suggested_label="no deterministic label refinement",
                    confidence=observation.confidence,
                    reason="Existing Afferens labels did not match the deterministic ambiguity rules.",
                )
            )

        summary = self._summary(observation, label_suggestions, safety_notes)
        return EnrichmentDraft(
            provider=self.provider_name,
            model=self.model_name,
            summary=summary,
            label_suggestions=label_suggestions,
            safety_notes=safety_notes,
            spatial_notes=spatial_notes,
        )

    @staticmethod
    def _summary(
        observation: Observation,
        label_suggestions: list[EnrichmentLabelSuggestion],
        safety_notes: list[str],
    ) -> str:
        object_count = len(observation.objects)
        ambiguity_count = len(
            [item for item in label_suggestions if item.suggested_label != "no deterministic label refinement"]
        )
        if object_count == 0:
            return "No objects were available in the latest Afferens observation for enrichment."
        if safety_notes:
            return (
                f"Deterministic enrichment reviewed {object_count} Afferens object(s), "
                f"found {ambiguity_count} possible label ambiguity item(s), and noted conservative safety context."
            )
        return (
            f"Deterministic enrichment reviewed {object_count} Afferens object(s) and found "
            f"{ambiguity_count} possible label ambiguity item(s)."
        )


class FireworksObservationEnrichmentProvider:
    provider_name = "fireworks"

    def __init__(self, adapter: FireworksReasoningAdapter, settings: Settings) -> None:
        self._adapter = adapter
        self._settings = settings
        self.model_name = settings.fireworks_model

    async def enrich(self, observation: Observation, *, focus: EnrichmentFocus) -> EnrichmentDraft:
        result = await self._adapter.enrich_observation(
            observation=observation.model_dump(mode="json"),
            focus=focus.value,
        )
        return EnrichmentDraft(
            provider=self.provider_name,
            model=self.model_name,
            summary=result.summary,
            label_suggestions=[
                EnrichmentLabelSuggestion.model_validate(item)
                for item in result.label_suggestions
            ],
            safety_notes=result.safety_notes,
            spatial_notes=result.spatial_notes,
        )


class GeminiObservationEnrichmentProvider:
    provider_name = "gemini"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.model_name = settings.gemini_model

    async def enrich(self, observation: Observation, *, focus: EnrichmentFocus) -> EnrichmentDraft:
        raise FireworksProviderUnavailable(
            "Gemini enrichment is an optional seam but is not implemented in this backend lane."
        )


class ObservationEnrichmentService:
    def __init__(
        self,
        data_spine: DataSpineService,
        *,
        settings: Settings,
        fireworks: FireworksReasoningAdapter,
    ) -> None:
        self._data_spine = data_spine
        self._settings = settings
        self._fireworks = fireworks
        self._deterministic = DeterministicObservationEnrichmentProvider()

    async def enrich_latest(self, request: EnrichmentLatestRequest) -> EnrichmentLatestResponse:
        observation = self._data_spine.latest_observation()
        if observation is None:
            started_at = utc_now()
            completed_at = utc_now()
            model_run = ModelRun(
                id=new_id("run"),
                provider=request.provider.value,
                model="none",
                state=ModelRunState.SKIPPED,
                started_at=started_at,
                completed_at=completed_at,
                latency_ms=0,
                error_message="No persisted Afferens observation is available.",
            )
            return EnrichmentLatestResponse(
                ok=False,
                observation_id=None,
                provider=request.provider.value,
                provider_state=EnrichmentProviderState.SKIPPED,
                model_run=model_run,
                enrichment=None,
                message="No Afferens observation is available to enrich. Sync live perception first.",
            )

        if request.provider == EnrichmentProvider.GEMINI:
            return self._unavailable_gemini_response(observation, request)

        if request.provider == EnrichmentProvider.DETERMINISTIC:
            draft = await self._deterministic.enrich(observation, focus=request.focus)
            return self._build_success_response(
                observation=observation,
                request=request,
                draft=draft,
                provider_state=EnrichmentProviderState.USED,
                message="Deterministic enrichment completed from Afferens-derived evidence.",
            )

        if request.provider in {EnrichmentProvider.AUTO, EnrichmentProvider.FIREWORKS}:
            if self._settings.fireworks_configured:
                started_at = utc_now()
                try:
                    draft = await FireworksObservationEnrichmentProvider(
                        self._fireworks,
                        self._settings,
                    ).enrich(observation, focus=request.focus)
                    return self._build_success_response(
                        observation=observation,
                        request=request,
                        draft=draft,
                        provider_state=EnrichmentProviderState.USED,
                        message="Fireworks enrichment completed from structured Afferens evidence.",
                        model_run_started_at=started_at,
                    )
                except (FireworksProviderUnavailable, FireworksProviderError, ValueError) as exc:
                    failed_run = self._model_run(
                        provider="fireworks",
                        model=self._settings.fireworks_model,
                        state=ModelRunState.FAILED,
                        error_message=str(exc),
                        started_at=started_at,
                    )
                    if request.persist:
                        self._data_spine.create_model_run(
                            failed_run,
                            observation_id=observation.id,
                            purpose="vision_enrichment",
                            focus=request.focus.value,
                        )

            draft = await self._deterministic.enrich(observation, focus=request.focus)
            message = (
                "Fireworks is not configured; deterministic enrichment used Afferens-derived evidence."
                if not self._settings.fireworks_configured
                else "Fireworks enrichment failed; deterministic enrichment used Afferens-derived evidence."
            )
            return self._build_success_response(
                observation=observation,
                request=request,
                draft=draft,
                provider_state=EnrichmentProviderState.FALLBACK,
                message=message,
            )

        draft = await self._deterministic.enrich(observation, focus=request.focus)
        return self._build_success_response(
            observation=observation,
            request=request,
            draft=draft,
            provider_state=EnrichmentProviderState.FALLBACK,
            message="Deterministic enrichment used Afferens-derived evidence.",
        )

    def latest_enrichment(self) -> ObservationEnrichment | None:
        return self._data_spine.latest_enrichment()

    def _unavailable_gemini_response(
        self,
        observation: Observation,
        request: EnrichmentLatestRequest,
    ) -> EnrichmentLatestResponse:
        model_run = self._model_run(
            provider="gemini",
            model=self._settings.gemini_model,
            state=ModelRunState.SKIPPED,
            error_message="Gemini enrichment is optional and not implemented/configured in this backend lane.",
        )
        if request.persist:
            self._data_spine.create_model_run(
                model_run,
                observation_id=observation.id,
                purpose="vision_enrichment",
                focus=request.focus.value,
            )
        return EnrichmentLatestResponse(
            ok=False,
            observation_id=observation.id,
            provider="gemini",
            provider_state=EnrichmentProviderState.UNAVAILABLE,
            model_run=model_run,
            enrichment=None,
            message="Gemini enrichment is unavailable. Use auto, fireworks, or deterministic.",
        )

    def _build_success_response(
        self,
        *,
        observation: Observation,
        request: EnrichmentLatestRequest,
        draft: EnrichmentDraft,
        provider_state: EnrichmentProviderState,
        message: str,
        model_run_started_at: datetime | None = None,
    ) -> EnrichmentLatestResponse:
        model_run = self._model_run(
            provider=draft.provider,
            model=draft.model,
            state=ModelRunState.COMPLETED,
            started_at=model_run_started_at,
        )
        enrichment = ObservationEnrichment(
            id=new_id("enrich"),
            observation_id=observation.id,
            source_provider=draft.provider,
            source_model=draft.model,
            summary=draft.summary,
            label_suggestions=draft.label_suggestions,
            safety_notes=draft.safety_notes,
            spatial_notes=draft.spatial_notes,
            evidence_observation_ids=[observation.id],
        )
        if request.persist:
            self._data_spine.create_model_run(
                model_run,
                observation_id=observation.id,
                purpose="vision_enrichment",
                focus=request.focus.value,
            )
            self._data_spine.create_observation_enrichment(
                enrichment,
                model_run_id=model_run.id,
            )
        return EnrichmentLatestResponse(
            ok=True,
            observation_id=observation.id,
            provider=draft.provider,
            provider_state=provider_state,
            model_run=model_run,
            enrichment=enrichment,
            message=message,
        )

    @staticmethod
    def _model_run(
        *,
        provider: str,
        model: str,
        state: ModelRunState,
        error_message: str | None = None,
        started_at: datetime | None = None,
    ) -> ModelRun:
        started_at = started_at or utc_now()
        completed_at = utc_now()
        latency_ms = max(0, int((completed_at - started_at).total_seconds() * 1000))
        return ModelRun(
            id=new_id("run"),
            provider=provider,
            model=model,
            state=state,
            started_at=started_at,
            completed_at=completed_at,
            latency_ms=latency_ms,
            error_message=error_message,
        )
