from __future__ import annotations

import hashlib
import math
import re
from collections import Counter


EMBEDDING_DIMENSIONS = 1536
LOCAL_EMBEDDING_PROVIDER = "deterministic_local"
TOKEN_RE = re.compile(r"[a-z0-9]+")

_SYNONYMS: dict[str, tuple[str, ...]] = {
    "bottle": ("water", "drink", "hydration", "container"),
    "cup": ("water", "drink", "hydration", "mug"),
    "glass": ("water", "drink", "hydration", "cup"),
    "water": ("drink", "hydration", "bottle", "cup"),
    "drink": ("water", "hydration", "bottle", "cup"),
    "hydration": ("water", "drink", "bottle", "cup"),
    "fall": ("fallen", "wellness", "check", "safety"),
    "fallen": ("fall", "wellness", "check", "safety"),
    "stillness": ("wellness", "check", "activity"),
    "wellness": ("safety", "check", "caregiver"),
    "reminder": ("message", "family", "prompt"),
    "message": ("reminder", "family", "prompt"),
    "note": ("care", "summary", "caregiver"),
    "diary": ("day", "summary", "activity"),
    "kitchen": ("room", "area", "table"),
    "living": ("room", "area", "sofa"),
    "bedroom": ("room", "area", "bed"),
}


class LocalDeterministicEmbeddingProvider:
    """Stable local embeddings for no-key/dev semantic retrieval.

    This is intentionally deterministic and provider-free. It gives the product
    a vector path without pretending to call an unavailable external embedding
    model.
    """

    provider_name = LOCAL_EMBEDDING_PROVIDER
    dimensions = EMBEDDING_DIMENSIONS

    def embed(self, text: str) -> list[float]:
        tokens = _expanded_tokens(text)
        if not tokens:
            return [0.0] * self.dimensions

        vector = [0.0] * self.dimensions
        counts = Counter(tokens)
        for token, count in counts.items():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = -1.0 if digest[4] % 2 else 1.0
            weight = 1.0 + math.log(count)
            vector[index] += sign * weight

        magnitude = math.sqrt(sum(value * value for value in vector))
        if magnitude == 0:
            return vector
        return [round(value / magnitude, 8) for value in vector]


def cosine_similarity(first: list[float] | None, second: list[float] | None) -> float:
    if not first or not second:
        return 0.0
    limit = min(len(first), len(second))
    if limit == 0:
        return 0.0
    dot = sum(first[index] * second[index] for index in range(limit))
    first_norm = math.sqrt(sum(value * value for value in first[:limit]))
    second_norm = math.sqrt(sum(value * value for value in second[:limit]))
    if first_norm == 0 or second_norm == 0:
        return 0.0
    return dot / (first_norm * second_norm)


def _expanded_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for token in TOKEN_RE.findall(text.lower()):
        if len(token) <= 1:
            continue
        normalized = _stem(token)
        tokens.append(normalized)
        tokens.extend(_SYNONYMS.get(normalized, ()))
    return tokens


def _stem(token: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if len(token) > len(suffix) + 3 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token
