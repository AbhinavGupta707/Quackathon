from __future__ import annotations

import importlib.util
from typing import Any

from app.afferens_adapter import AfferensAdapter
from app.config import Settings
from app.embeddings import EMBEDDING_DIMENSIONS, LOCAL_EMBEDDING_PROVIDER
from app.schemas import (
    ActionRuntimeFallStatus,
    AfferensConnectionState,
    ProviderReadinessState,
    ProviderStatus,
    ProvidersStatusResponse,
)
from app.actuation import SAFE_AFFERENS_COMMANDS
from app.yolo_fall_adapter import UltralyticsFallAdapter


class ProviderStatusService:
    def __init__(
        self,
        settings: Settings,
        *,
        afferens: AfferensAdapter,
        fall_adapter: UltralyticsFallAdapter,
    ) -> None:
        self._settings = settings
        self._afferens = afferens
        self._fall_adapter = fall_adapter

    async def status(self) -> ProvidersStatusResponse:
        providers = [
            await self._afferens_status(),
            self._fireworks_status(),
            self._langsmith_status(),
            self._gemini_status(),
            self._parcle_status(),
            self._semantic_memory_status(),
            self._action_runtime_status(),
        ]
        return ProvidersStatusResponse(ok=True, providers=providers)

    async def _afferens_status(self) -> ProviderStatus:
        result = await self._afferens.fetch_latest()
        status = result.status
        details: dict[str, Any] = {
            "base_url": status.base_url,
            "checked_modality": "VISION",
        }
        if status.latest_event_id:
            details["latest_event_id"] = status.latest_event_id
        if status.source_node_id:
            details["source_node_id"] = status.source_node_id

        if status.state == AfferensConnectionState.LIVE:
            return ProviderStatus(
                provider="afferens",
                state=ProviderReadinessState.LIVE,
                message="Afferens key is configured and Vision has live events.",
                details=details,
            )
        if status.state == AfferensConnectionState.MISSING_KEY:
            return ProviderStatus(
                provider="afferens",
                state=ProviderReadinessState.MISSING_KEY,
                message="Afferens API key is not configured.",
                details=details,
            )
        if status.state in {
            AfferensConnectionState.INVALID_KEY,
            AfferensConnectionState.INACTIVE_KEY,
        }:
            return ProviderStatus(
                provider="afferens",
                state=ProviderReadinessState.UNAVAILABLE,
                message=status.message,
                details=details,
            )
        return ProviderStatus(
            provider="afferens",
            state=ProviderReadinessState.DEGRADED,
            message=status.message,
            details=details,
        )

    def _fireworks_status(self) -> ProviderStatus:
        if not self._settings.fireworks_configured:
            return ProviderStatus(
                provider="fireworks",
                state=ProviderReadinessState.MISSING_KEY,
                message="Fireworks API key is not configured; deterministic fallback is available.",
                details={"model": self._settings.fireworks_model},
            )
        return ProviderStatus(
            provider="fireworks",
            state=ProviderReadinessState.CONFIGURED,
            message="Fireworks key is configured; live smoke is not run by this status request.",
            details={"model": self._settings.fireworks_model},
        )

    def _langsmith_status(self) -> ProviderStatus:
        sdk_installed = importlib.util.find_spec("langsmith") is not None
        details = {
            "project": self._settings.langsmith_project,
            "sdk_installed": sdk_installed,
            "trace_content_enabled": self._settings.langsmith_trace_content,
        }
        if not self._settings.langsmith_tracing:
            return ProviderStatus(
                provider="langsmith",
                state=ProviderReadinessState.DISABLED,
                message="LangSmith tracing is disabled unless LANGSMITH_TRACING=true.",
                details=details,
            )
        if not self._settings.langsmith_configured:
            return ProviderStatus(
                provider="langsmith",
                state=ProviderReadinessState.MISSING_KEY,
                message="LangSmith tracing is requested but LANGSMITH_API_KEY is not configured.",
                details=details,
            )
        if not sdk_installed:
            return ProviderStatus(
                provider="langsmith",
                state=ProviderReadinessState.UNAVAILABLE,
                message="LangSmith SDK is not installed; tracing is unavailable.",
                details=details,
            )
        return ProviderStatus(
            provider="langsmith",
            state=ProviderReadinessState.CONFIGURED,
            message="LangSmith tracing is configured with content redaction controlled by settings.",
            details=details,
        )

    def _gemini_status(self) -> ProviderStatus:
        return ProviderStatus(
            provider="gemini",
            state=ProviderReadinessState.DEFERRED,
            message="Gemini is an optional privacy-gated enrichment provider and is not implemented as a live runtime dependency.",
            details={
                "key_configured": self._settings.gemini_configured,
                "model": self._settings.gemini_model,
            },
        )

    def _parcle_status(self) -> ProviderStatus:
        return ProviderStatus(
            provider="parcle",
            state=ProviderReadinessState.DEFERRED,
            message="Parcle/Parcel memory is not implemented in this build.",
            details={
                "aliases": ["parcel"],
                "key_configured": self._settings.parcle_configured
                or self._settings.parcel_configured,
            },
        )

    def _semantic_memory_status(self) -> ProviderStatus:
        requested_provider = self._settings.embedding_provider_normalized
        external_requested = requested_provider not in {"", "none", "disabled", "local", "deterministic_local"}
        return ProviderStatus(
            provider="semantic_memory",
            state=ProviderReadinessState.VECTOR_ENABLED,
            message=(
                "Semantic memory uses hybrid lexical plus local deterministic vector retrieval "
                "stored in pgvector-ready columns; external memory mirrors remain deferred."
            ),
            details={
                "semantic_memory_enabled": self._settings.semantic_memory_enabled,
                "pgvector_schema_ready": True,
                "embedding_provider": LOCAL_EMBEDDING_PROVIDER,
                "embedding_dimensions": EMBEDDING_DIMENSIONS,
                "requested_embedding_provider": requested_provider,
                "external_embedding_provider_requested": external_requested,
                "external_embedding_provider_active": False,
                "embedding_configured": True,
                "vector_retrieval_enabled": True,
                "lexical_fallback_enabled": True,
                "retrieval_mode": "hybrid",
                "parcel_memory_mirror": "deferred",
            },
        )

    def _action_runtime_status(self) -> ProviderStatus:
        fall = self._fall_adapter.status()
        fall_details = self._safe_fall_details(fall)
        details = {
            "fall": fall_details,
            "drink": {
                "provider": "browser_mediapipe",
                "available": True,
                "enabled": True,
            },
            "afferens_actuation": self._actuation_details(),
            "privacy": {
                "raw_video_storage_enabled": self._settings.action_raw_video_storage_enabled,
                "raw_frames_persisted": False,
            },
        }
        if fall.available:
            return ProviderStatus(
                provider="action_runtime",
                state=ProviderReadinessState.CONFIGURED,
                message="Action runtime is ready for browser MediaPipe drink candidates and configured YOLO fall inference.",
                details=details,
            )
        return ProviderStatus(
            provider="action_runtime",
            state=ProviderReadinessState.DEGRADED,
            message="Browser MediaPipe drink candidates are available; YOLO fall inference is not ready.",
            details=details,
        )

    @staticmethod
    def _safe_fall_details(status: ActionRuntimeFallStatus) -> dict[str, Any]:
        return {
            "provider": status.provider,
            "enabled": status.enabled,
            "available": status.available,
            "state": status.state,
            "model_path_configured": status.model_path_configured,
            "model_file_exists": status.model_file_exists,
            "model_loaded": status.model_loaded,
            "labels": status.labels,
            "unavailable_reason": status.unavailable_reason,
            "model_metadata": status.model_metadata,
        }

    def _actuation_details(self) -> dict[str, Any]:
        configured_commands = self._settings.afferens_supported_actuation_commands
        safe_configured = sorted(configured_commands & SAFE_AFFERENS_COMMANDS)
        unsafe_configured = sorted(configured_commands - SAFE_AFFERENS_COMMANDS)
        return {
            "enabled": self._settings.afferens_actuation_enabled,
            "state": "configured" if self._settings.afferens_actuation_enabled else "disabled",
            "safe_commands": sorted(SAFE_AFFERENS_COMMANDS),
            "safe_commands_configured": safe_configured,
            "unsafe_configured_commands_ignored": unsafe_configured,
            "requires_task_or_alert_linkage": True,
            "requires_live_evidence_linkage": True,
            "resolution_requires": "live_verification_or_human_ack",
        }
