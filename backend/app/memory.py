from __future__ import annotations

from app.repositories import DataRepository
from app.schemas import LastSeenObject, Observation


class ObjectMemoryService:
    def __init__(self, repository: DataRepository) -> None:
        self._repository = repository

    def update_from_observation(self, observation: Observation) -> list[LastSeenObject]:
        if not observation.objects:
            return []
        return self._repository.upsert_last_seen_objects(observation)
