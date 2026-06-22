from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.main import create_app
from app.models import Base
from app.providers.fireworks import FireworksProviderError, FireworksReasoningAdapter
from app.repositories import InMemoryDataRepository
from app.routes.dependencies import (
    get_app_settings,
    get_data_spine_service,
    get_fireworks_reasoning_adapter,
)
from app.schemas import (
    AlertSeverity,
    CareNote,
    CareNoteAudience,
    DailyDiaryEntry,
    FamilyMessage,
    HydrationEvent,
    HydrationEventType,
    QueryConfidence,
    SemanticMemoryAskRequest,
    WellnessCheck,
    WellnessCheckStatus,
    WellnessCheckType,
    utc_now,
)
from app.semantic_memory import SemanticMemoryService
from app.services import DataSpineService
from app.sql_repository import SQLAlchemyDataRepository


def _settings() -> Settings:
    return Settings(
        environment="test",
        afferens_base_url="https://afferens.test",
        afferens_api_key="test-api-key",
        fireworks_api_key=None,
    )


def _seed_memory(service: DataSpineService, repository: InMemoryDataRepository) -> str:
    service.sync_raw_events(
        [
            {
                "entity_id": "LIVE-C7-BOTTLE",
                "timestamp_utc": "2026-06-21T16:00:00Z",
                "objects": [
                    {
                        "label": "bottle",
                        "confidence": 0.86,
                        "relative_location": "on the kitchen table",
                    }
                ],
            }
        ],
        room_id="kitchen_zone",
    )
    observation_id = repository.last_seen["bottle"].last_seen_observation_id
    repository.upsert_daily_diary(
        DailyDiaryEntry(
            id="diary_c7",
            date=date(2026, 6, 21),
            summary="Water bottle activity appeared around the kitchen table.",
            highlights=["Bottle seen once."],
            needs_review=["Please verify hydration if it matters."],
            evidence_ids=[observation_id],
            generated_at=datetime(2026, 6, 21, 20, tzinfo=timezone.utc),
        )
    )
    repository.create_care_note(
        CareNote(
            id="care_c7",
            date=date(2026, 6, 21),
            audience=CareNoteAudience.FAMILY,
            summary="Bottle was visible in the kitchen zone.",
            bullets=["Kitchen table had a bottle."],
            risks=[],
            follow_ups=["Check hydration gently."],
            evidence_ids=[observation_id],
            created_at=datetime(2026, 6, 21, 21, tzinfo=timezone.utc),
        )
    )
    repository.create_family_message(
        FamilyMessage(
            id="fam_c7",
            title="Water reminder",
            body="Your water bottle is usually on the kitchen table.",
            trigger_object_key="bottle",
            created_at=datetime(2026, 6, 21, 9, tzinfo=timezone.utc),
        )
    )
    repository.create_hydration_event(
        HydrationEvent(
            id="hyd_c7",
            type=HydrationEventType.WATER_VISIBLE,
            occurred_at=datetime(2026, 6, 21, 16, 5, tzinfo=timezone.utc),
            confidence=QueryConfidence.MEDIUM,
            zone_id="kitchen_zone",
            zone_name="Kitchen table",
            evidence_ids=[observation_id],
            metadata={"object_keys": ["bottle"], "source": "afferens_observation"},
        )
    )
    repository.create_wellness_check(
        WellnessCheck(
            id="well_c7",
            type=WellnessCheckType.HYDRATION_PROMPT,
            severity=AlertSeverity.LOW,
            status=WellnessCheckStatus.OPEN,
            title="Hydration reminder",
            body="Limited water-nearby evidence appeared today. Consider a gentle reminder.",
            confidence=QueryConfidence.LOW,
            occurred_at=datetime(2026, 6, 21, 18, tzinfo=timezone.utc),
            evidence_ids=[observation_id],
        )
    )
    return observation_id


def _semantic_service(
    service: DataSpineService,
    fireworks: Any | None = None,
) -> SemanticMemoryService:
    return SemanticMemoryService(
        service,
        fireworks=fireworks or FireworksReasoningAdapter(_settings()),
    )


def test_semantic_reindex_is_idempotent_and_indexes_existing_memory_sources() -> None:
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)
    observation_id = _seed_memory(service, repository)
    semantic = _semantic_service(service)

    first = semantic.reindex()
    second = semantic.reindex()

    assert first.created_count == 7
    assert first.updated_count == 0
    assert first.skipped_count == 0
    assert second.created_count == 0
    assert second.updated_count == 0
    assert second.skipped_count == 7
    assert len(repository.semantic_memory) == 7
    assert all(item.source_ids for item in repository.semantic_memory.values())
    assert observation_id in {
        evidence_id for item in repository.semantic_memory.values() for evidence_id in item.evidence_ids
    }


def test_semantic_search_returns_cited_lexical_results() -> None:
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)
    observation_id = _seed_memory(service, repository)
    semantic = _semantic_service(service)
    semantic.reindex()

    response = semantic.semantic(query="kitchen bottle hydration", limit=5)

    assert response.ok is True
    assert response.items
    assert response.items[0].score > 0
    assert response.items[0].source_ids
    assert observation_id in {
        evidence_id for item in response.items for evidence_id in item.evidence_ids
    }


async def test_semantic_ask_uses_deterministic_fallback_when_fireworks_unavailable() -> None:
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)
    observation_id = _seed_memory(service, repository)
    semantic = _semantic_service(service)

    response = await semantic.ask(
        SemanticMemoryAskRequest(question="What do we know about the kitchen bottle?")
    )

    assert response.ok is True
    assert response.provider == "hybrid_local_vector"
    assert response.used_memory is True
    assert response.needs_human_verification is True
    assert response.citations
    assert response.citations[0].embedding
    assert observation_id in response.evidence_ids
    assert "Please verify" in response.answer


async def test_semantic_ask_does_not_answer_without_cited_memory() -> None:
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)
    semantic = _semantic_service(service)

    response = await semantic.ask(SemanticMemoryAskRequest(question="What about the keys?"))

    assert response.ok is True
    assert response.used_memory is False
    assert response.evidence_ids == []
    assert response.source_ids == []
    assert response.citations == []
    assert "do not have cited memory" in response.answer


class FailingFireworks:
    async def synthesize_semantic_answer(self, **_: Any) -> Any:
        raise FireworksProviderError("boom")


async def test_semantic_ask_falls_back_when_fireworks_synthesis_fails() -> None:
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)
    _seed_memory(service, repository)
    semantic = _semantic_service(service, fireworks=FailingFireworks())

    response = await semantic.ask(SemanticMemoryAskRequest(question="Where is the bottle?"))

    assert response.provider == "hybrid_local_vector"
    assert response.used_memory is True
    assert response.citations


def test_semantic_memory_routes_reindex_search_and_ask() -> None:
    app = create_app()
    settings = _settings()
    repository = InMemoryDataRepository()
    service = DataSpineService(repository)
    observation_id = _seed_memory(service, repository)
    app.dependency_overrides[get_app_settings] = lambda: settings
    app.dependency_overrides[get_data_spine_service] = lambda: service
    app.dependency_overrides[get_fireworks_reasoning_adapter] = lambda: FireworksReasoningAdapter(
        settings
    )
    client = TestClient(app)

    reindex_response = client.post("/api/memory/reindex", json={})
    assert reindex_response.status_code == 200
    assert reindex_response.json()["indexed_count"] == 7
    assert reindex_response.json()["provider"] == "hybrid_local_vector"
    assert reindex_response.json()["embedding_provider"] == "deterministic_local"

    search_response = client.get("/api/memory/semantic?q=bottle&limit=3")
    search_payload = search_response.json()
    assert search_response.status_code == 200
    assert search_payload["provider"] == "hybrid_local_vector"
    assert search_payload["retrieval_mode"] == "hybrid"
    assert search_payload["items"]
    assert search_payload["items"][0]["source_ids"]

    ask_response = client.post(
        "/api/memory/ask",
        json={"question": "What memory is there about the bottle?"},
    )
    ask_payload = ask_response.json()
    assert ask_response.status_code == 200
    assert ask_payload["used_memory"] is True
    assert observation_id in ask_payload["evidence_ids"]
    assert ask_payload["citations"]
    assert "test-api-key" not in ask_response.text


def test_sql_repository_persists_semantic_memory_items() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    repository = SQLAlchemyDataRepository(session_factory)
    service = DataSpineService(repository)
    service.sync_raw_events(
        [
            {
                "entity_id": "LIVE-SQL-BOTTLE",
                "timestamp_utc": "2026-06-21T16:00:00Z",
                "objects": [{"label": "bottle", "relative_location": "on the side table"}],
            }
        ],
        room_id="living_room",
    )
    semantic = _semantic_service(service)

    first = semantic.reindex()
    second = semantic.reindex()
    response = semantic.semantic(query="side table bottle", limit=5)

    assert first.created_count == 2
    assert second.skipped_count == 2
    assert response.items
    assert response.items[0].source_ids
    assert response.items[0].embedding
    assert any("LIVE-SQL-BOTTLE" not in item.text for item in response.items)
    assert utc_now() is not None
