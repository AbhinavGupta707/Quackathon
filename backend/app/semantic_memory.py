from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from app.embeddings import (
    LOCAL_EMBEDDING_PROVIDER,
    LocalDeterministicEmbeddingProvider,
    cosine_similarity,
)
from app.providers.fireworks import (
    FireworksProviderError,
    FireworksProviderUnavailable,
    FireworksReasoningAdapter,
)
from app.schemas import (
    QueryConfidence,
    SemanticMemoryAskRequest,
    SemanticMemoryAskResponse,
    SemanticMemoryReindexResponse,
    SemanticMemoryResult,
    SemanticMemorySearchResponse,
    SemanticMemorySourceType,
)
from app.services import DataSpineService


LEXICAL_PROVIDER = "deterministic_lexical"
HYBRID_PROVIDER = "hybrid_local_vector"
FIREWORKS_PROVIDER = "fireworks"
TOKEN_RE = re.compile(r"[a-z0-9]+")
STOP_WORDS = {
    "a",
    "about",
    "an",
    "and",
    "are",
    "at",
    "did",
    "do",
    "for",
    "from",
    "has",
    "have",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "the",
    "there",
    "to",
    "was",
    "were",
    "what",
    "when",
    "where",
    "with",
}


@dataclass(frozen=True)
class SemanticSearch:
    results: list[SemanticMemoryResult]
    reindex_recommended: bool = False
    used_vector: bool = False


class SemanticMemoryService:
    def __init__(
        self,
        data_spine: DataSpineService,
        *,
        fireworks: FireworksReasoningAdapter,
        embeddings: LocalDeterministicEmbeddingProvider | None = None,
    ) -> None:
        self._data_spine = data_spine
        self._fireworks = fireworks
        self._embeddings = embeddings or LocalDeterministicEmbeddingProvider()

    def reindex(
        self,
        *,
        force: bool = False,
        source_types: list[SemanticMemorySourceType] | None = None,
    ) -> SemanticMemoryReindexResponse:
        source_items = self._data_spine.list_semantic_source_items(source_types=source_types)
        embedded_items = [
            item.model_copy(update={"embedding": self._embed_item(item)}) for item in source_items
        ]
        created, updated, skipped = self._data_spine.upsert_semantic_memory_items(
            embedded_items,
            force=force,
        )
        return SemanticMemoryReindexResponse(
            ok=True,
            provider=HYBRID_PROVIDER,
            embedding_provider=LOCAL_EMBEDDING_PROVIDER,
            retrieval_mode="hybrid",
            indexed_count=len(source_items),
            created_count=created,
            updated_count=updated,
            skipped_count=skipped,
            message=(
                "Semantic memory reindexed from existing evidence-backed local records "
                f"with {LOCAL_EMBEDDING_PROVIDER} embeddings for hybrid lexical/vector retrieval."
                if source_items
                else "No source records were available to index yet."
            ),
        )

    def semantic(
        self,
        *,
        query: str | None,
        limit: int,
        source_types: list[SemanticMemorySourceType] | None = None,
    ) -> SemanticMemorySearchResponse:
        search = self.search(query=query, limit=limit, source_types=source_types)
        return SemanticMemorySearchResponse(
            query=query,
            provider=HYBRID_PROVIDER if search.used_vector else LEXICAL_PROVIDER,
            embedding_provider=LOCAL_EMBEDDING_PROVIDER if search.used_vector else None,
            retrieval_mode="hybrid" if search.used_vector else "lexical",
            reindex_recommended=search.reindex_recommended,
            items=search.results,
        )

    def search(
        self,
        *,
        query: str | None,
        limit: int,
        source_types: list[SemanticMemorySourceType] | None = None,
    ) -> SemanticSearch:
        indexed = self._data_spine.list_semantic_memory_items(source_types=source_types)
        if not indexed:
            return SemanticSearch(results=[], reindex_recommended=True)

        if query is None or not query.strip():
            results = [
                self._result_from_item(item, score=1.0, match_reasons=["recent indexed memory"])
                for item in indexed[:limit]
            ]
            return SemanticSearch(results=results)

        query_tokens = self._tokens(query)
        if not query_tokens:
            return SemanticSearch(results=[])

        query_embedding = self._embeddings.embed(query)
        scored: list[SemanticMemoryResult] = []
        for item in indexed:
            score, reasons = self._score(item, query, query_tokens, query_embedding)
            if score <= 0:
                continue
            scored.append(self._result_from_item(item, score=score, match_reasons=reasons))

        scored.sort(key=lambda item: (item.score, item.occurred_at or item.created_at), reverse=True)
        return SemanticSearch(
            results=scored[:limit],
            used_vector=any("vector similarity" in reason for item in scored for reason in item.match_reasons),
        )

    async def ask(self, request: SemanticMemoryAskRequest) -> SemanticMemoryAskResponse:
        if not self._data_spine.list_semantic_memory_items(source_types=request.source_types):
            self.reindex(source_types=request.source_types)

        search = self.search(
            query=request.question,
            limit=request.limit,
            source_types=request.source_types,
        )
        citations = [item for item in search.results if item.source_ids]
        if not citations:
            return SemanticMemoryAskResponse(
                ok=True,
                answer=(
                    "I do not have cited memory that answers that yet. "
                    "Use live Afferens evidence or caregiver-entered notes first, then reindex memory."
                ),
                confidence=QueryConfidence.LOW,
                provider=LEXICAL_PROVIDER,
                used_memory=False,
                evidence_ids=[],
                source_ids=[],
                citations=[],
            )

        deterministic_answer = self._deterministic_answer(request.question, citations)
        confidence = self._confidence(citations[0].score)
        evidence_ids = self._unique([evidence_id for item in citations for evidence_id in item.evidence_ids])
        source_ids = self._unique([source_id for item in citations for source_id in item.source_ids])

        synthesized = await self._synthesize_if_available(request.question, citations)
        if synthesized is not None and synthesized.answer.strip():
            return SemanticMemoryAskResponse(
                ok=True,
                answer=synthesized.answer.strip(),
                confidence=self._min_confidence(confidence, synthesized.confidence),
                provider=FIREWORKS_PROVIDER,
                used_memory=True,
                needs_human_verification=True,
                evidence_ids=evidence_ids,
                source_ids=source_ids,
                citations=citations,
            )

        return SemanticMemoryAskResponse(
            ok=True,
            answer=deterministic_answer,
            confidence=confidence,
            provider=HYBRID_PROVIDER if self._citations_used_vector(citations) else LEXICAL_PROVIDER,
            used_memory=True,
            needs_human_verification=True,
            evidence_ids=evidence_ids,
            source_ids=source_ids,
            citations=citations,
        )

    async def _synthesize_if_available(
        self,
        question: str,
        citations: list[SemanticMemoryResult],
    ):
        try:
            return await self._fireworks.synthesize_semantic_answer(
                question=question,
                citations=[
                    {
                        "source_type": item.source_type.value,
                        "source_id": item.source_id,
                        "title": item.title,
                        "text": item.text,
                        "evidence_ids": item.evidence_ids,
                        "source_ids": item.source_ids,
                    }
                    for item in citations
                ],
            )
        except (FireworksProviderUnavailable, FireworksProviderError, ValueError):
            return None

    def _deterministic_answer(
        self,
        question: str,
        citations: list[SemanticMemoryResult],
    ) -> str:
        del question
        top = citations[0]
        answer = f"From cited memory, {top.text}"
        if len(citations) > 1:
            answer += f" I found {len(citations)} related cited memory items."
        return f"{answer} Please verify important details in person."

    def _score(
        self,
        item: SemanticMemoryResult | Any,
        query: str,
        query_tokens: list[str],
        query_embedding: list[float],
    ) -> tuple[float, list[str]]:
        haystack = self._search_text(item)
        haystack_tokens = Counter(self._tokens(haystack))
        lexical_score = 0.0
        reasons: list[str] = []
        for token in query_tokens:
            count = haystack_tokens.get(token, 0)
            if not count:
                continue
            lexical_score += min(count, 3)
            reasons.append(f"matched '{token}'")
        normalized_query = " ".join(query.lower().split())
        if normalized_query and normalized_query in haystack.lower():
            lexical_score += 2.0
            reasons.append("matched phrase")

        similarity = cosine_similarity(query_embedding, item.embedding)
        vector_score = 0.0
        if similarity >= 0.18:
            vector_score = similarity * 5.0
            reasons.append(f"vector similarity {similarity:.2f}")

        score = lexical_score + vector_score
        if item.evidence_ids:
            score += 0.15
        if item.source_ids:
            score += 0.1
        return score, list(dict.fromkeys(reasons))

    def _search_text(self, item: Any) -> str:
        metadata_text = " ".join(str(value) for value in item.metadata.values() if value is not None)
        return f"{item.title} {item.text} {item.source_type.value} {metadata_text}"

    def _embed_item(self, item: Any) -> list[float]:
        return self._embeddings.embed(self._search_text(item))

    def _result_from_item(
        self,
        item: Any,
        *,
        score: float,
        match_reasons: list[str],
    ) -> SemanticMemoryResult:
        return SemanticMemoryResult(
            **item.model_dump(),
            score=round(score, 4),
            match_reasons=match_reasons,
        )

    def _tokens(self, text: str) -> list[str]:
        return [
            token
            for token in TOKEN_RE.findall(text.lower())
            if token not in STOP_WORDS and len(token) > 1
        ]

    def _confidence(self, score: float) -> QueryConfidence:
        if score >= 4.0:
            return QueryConfidence.HIGH
        if score >= 1.5:
            return QueryConfidence.MEDIUM
        return QueryConfidence.LOW

    def _min_confidence(
        self,
        first: QueryConfidence,
        second: QueryConfidence,
    ) -> QueryConfidence:
        order = [QueryConfidence.LOW, QueryConfidence.MEDIUM, QueryConfidence.HIGH]
        return order[min(order.index(first), order.index(second))]

    def _unique(self, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value for value in values if value))

    def _citations_used_vector(self, citations: list[SemanticMemoryResult]) -> bool:
        return any(
            "vector similarity" in reason
            for item in citations
            for reason in item.match_reasons
        )
