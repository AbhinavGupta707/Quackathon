from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from app.schemas import DetectedObject, LastSeenObject


STOP_WORDS = {
    "a",
    "an",
    "are",
    "can",
    "could",
    "did",
    "find",
    "for",
    "have",
    "help",
    "i",
    "is",
    "it",
    "last",
    "locate",
    "located",
    "me",
    "my",
    "please",
    "see",
    "seen",
    "show",
    "the",
    "this",
    "to",
    "was",
    "were",
    "where",
}

ALIASES = {
    "cell": "phone",
    "cellphone": "phone",
    "key": "keys",
    "keychain": "keys",
    "keyring": "keys",
    "med": "medicine",
    "medication": "medicine",
    "meds": "medicine",
    "mobile": "phone",
    "pill": "medicine",
    "pill_bottle": "medicine",
    "pills": "medicine",
    "remote_control": "remote",
    "wallets": "wallet",
}


@dataclass(frozen=True)
class ObjectSearchCandidate:
    object_key: str
    display_name: str


def normalize_object_key(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    return ALIASES.get(normalized, normalized)


def object_candidates(
    *,
    memories: Iterable[LastSeenObject],
    observation_objects: Iterable[DetectedObject],
) -> list[ObjectSearchCandidate]:
    candidates: dict[str, ObjectSearchCandidate] = {}
    for memory in memories:
        candidates[memory.object_key] = ObjectSearchCandidate(
            object_key=memory.object_key,
            display_name=memory.display_name,
        )
    for detected in observation_objects:
        candidates.setdefault(
            detected.object_key,
            ObjectSearchCandidate(
                object_key=detected.object_key,
                display_name=detected.display_name,
            ),
        )
    return sorted(candidates.values(), key=lambda item: item.object_key)


def infer_object_key_from_query(
    query: str,
    candidates: Iterable[ObjectSearchCandidate],
) -> str | None:
    normalized_query = normalize_object_key(query)
    query_words = {
        normalize_object_key(word)
        for word in re.findall(r"[a-z0-9]+", query.lower())
        if word not in STOP_WORDS
    }

    scored: list[tuple[int, str]] = []
    for candidate in candidates:
        key = normalize_object_key(candidate.object_key)
        display = normalize_object_key(candidate.display_name)
        key_words = set(key.split("_")) | set(display.split("_"))
        singular_words = {word[:-1] for word in key_words if word.endswith("s") and len(word) > 3}
        all_words = key_words | singular_words | {ALIASES.get(word, word) for word in key_words}

        score = 0
        if key and key in normalized_query:
            score += 5
        if display and display in normalized_query:
            score += 4
        if query_words & all_words:
            score += 3
        if ALIASES.get(key) in query_words:
            score += 2
        if score:
            scored.append((score, candidate.object_key))

    if not scored:
        for word in query_words:
            if word in ALIASES.values() or word in ALIASES:
                return ALIASES.get(word, word)
        return None

    scored.sort(key=lambda item: (-item[0], item[1]))
    return scored[0][1]


def looks_like_object_location_query(query: str) -> bool:
    words = set(re.findall(r"[a-z0-9]+", query.lower()))
    location_words = {"find", "last", "locate", "located", "see", "seen", "where"}
    return bool(words & location_words)
