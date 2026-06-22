from __future__ import annotations

from app.repositories import DataRepository
from app.schemas import LastSeenObject, Observation


class ObjectMemoryService:
    def __init__(self, repository: DataRepository, *, recent_window_seconds: int = 300) -> None:
        self._repository = repository
        self._recent_window_seconds = recent_window_seconds

    def update_from_observation(self, observation: Observation) -> list[LastSeenObject]:
        return self._repository.upsert_last_seen_objects(
            observation,
            recent_window_seconds=self._recent_window_seconds,
        )
