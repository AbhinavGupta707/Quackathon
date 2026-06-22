"use client";

import { FormEvent, useState } from "react";
import { isUnavailableEndpoint, reindexSemanticMemory, searchSemanticMemory } from "@/lib/api";
import { formatDateTime, sentenceCase } from "@/lib/format";
import type {
  SemanticMemoryReindexResponse,
  SemanticMemoryResult,
  SemanticMemorySearchResponse,
  SemanticMemorySourceType
} from "@/lib/types";
import { EvidenceRefs } from "./EvidenceRefs";
import { StateBlock } from "./StateBlock";
import { StatusPill, type StatusTone } from "./StatusPill";

const SOURCE_FILTERS: Array<{ label: string; value: SemanticMemorySourceType | "" }> = [
  { label: "All sources", value: "" },
  { label: "Observations", value: "observation" },
  { label: "Object memory", value: "object_memory" },
  { label: "Diary", value: "diary_entry" },
  { label: "Care notes", value: "care_note" },
  { label: "Family messages", value: "family_message" },
  { label: "Hydration", value: "hydration_event" },
  { label: "Wellness", value: "wellness_check" }
];

export function CaregiverSemanticMemoryReview() {
  const [query, setQuery] = useState("What happened today?");
  const [sourceType, setSourceType] = useState<SemanticMemorySourceType | "">("");
  const [searchResult, setSearchResult] = useState<SemanticMemorySearchResponse | null>(null);
  const [reindexResult, setReindexResult] = useState<SemanticMemoryReindexResponse | null>(null);
  const [message, setMessage] = useState<{ tone?: "error" | "success"; title: string; body: string } | null>(null);
  const [loading, setLoading] = useState<"search" | "reindex" | null>(null);

  async function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) {
      setMessage({ title: "Enter a memory search", body: "Use a question or phrase such as bottle in kitchen." });
      return;
    }

    setLoading("search");
    setMessage(null);
    setSearchResult(null);

    try {
      const response = await searchSemanticMemory({ query: trimmed, sourceType, limit: 10 });
      setSearchResult(response);
    } catch (error) {
      setMessage(endpointMessage(error, "Semantic memory search is not available yet."));
    } finally {
      setLoading(null);
    }
  }

  async function handleReindex() {
    setLoading("reindex");
    setMessage(null);
    setReindexResult(null);

    try {
      const response = await reindexSemanticMemory();
      setReindexResult(response);
      setMessage({
        tone: "success",
        title: "Memory index refreshed",
        body: response.message || `Indexed ${response.indexed_count} memory rows.`
      });
    } catch (error) {
      setMessage(endpointMessage(error, "Semantic memory indexing is not available yet."));
    } finally {
      setLoading(null);
    }
  }

  return (
    <section className="review-card semantic-memory-review" aria-labelledby="semantic-memory-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Semantic Memory</p>
          <h2 id="semantic-memory-title">Search care memories</h2>
        </div>
        <StatusPill
          label={searchResult ? `${searchResult.items.length} results` : reindexResult ? "Indexed" : "Ready"}
          tone={statusTone(searchResult, reindexResult, message)}
        />
      </div>

      <form className="semantic-search-form" onSubmit={handleSearch}>
        <label className="semantic-search-form__wide">
          Search
          <input
            onChange={(event) => setQuery(event.target.value)}
            placeholder="What happened this morning?"
            type="text"
            value={query}
          />
        </label>
        <label>
          Source
          <select
            onChange={(event) => setSourceType(event.target.value as SemanticMemorySourceType | "")}
            value={sourceType}
          >
            {SOURCE_FILTERS.map((source) => (
              <option key={source.label} value={source.value}>
                {source.label}
              </option>
            ))}
          </select>
        </label>
        <div className="semantic-search-form__actions">
          <button className="button button--primary" disabled={loading === "search"} type="submit">
            {loading === "search" ? "Searching" : "Search"}
          </button>
          <button className="button button--secondary" disabled={loading === "reindex"} onClick={() => void handleReindex()} type="button">
            {loading === "reindex" ? "Refreshing" : "Refresh index"}
          </button>
        </div>
      </form>

      {message ? (
        <StateBlock tone={message.tone === "error" ? "error" : message.tone === "success" ? "success" : "empty"} title={message.title} body={message.body} />
      ) : null}

      {reindexResult ? (
        <dl className="compact-meta compact-meta--two">
          <div>
            <dt>Indexed</dt>
            <dd>{reindexResult.indexed_count}</dd>
          </div>
          <div>
            <dt>Skipped</dt>
            <dd>{reindexResult.skipped_count}</dd>
          </div>
          <div>
            <dt>Changed</dt>
            <dd>{reindexResult.created_count + reindexResult.updated_count}</dd>
          </div>
          <div>
            <dt>Index type</dt>
            <dd>{reindexResult.provider || "Unavailable"}</dd>
          </div>
          <div>
            <dt>Status</dt>
            <dd>{reindexResult.ok ? "Complete" : "Needs review"}</dd>
          </div>
        </dl>
      ) : null}

      <SearchResults result={searchResult} loading={loading === "search"} />
    </section>
  );
}

function SearchResults({
  loading,
  result
}: {
  loading: boolean;
  result: SemanticMemorySearchResponse | null;
}) {
  if (loading) {
    return <StateBlock tone="loading" title="Searching memories" body="Looking across indexed observations and care notes." />;
  }

  if (!result) {
    return (
      <StateBlock
        title="Search broad care memory"
        body="Use this to review evidence-backed memories across observations, diary notes, care notes, family messages, hydration, and wellness checks."
      />
    );
  }

  if (result.items.length === 0) {
    return (
      <>
        <SemanticSearchProvenance result={result} />
        <StateBlock title="No matching memory rows" body="Try a broader phrase or refresh the memory index." />
      </>
    );
  }

  return (
    <>
      <SemanticSearchProvenance result={result} />
      <div className="semantic-result-list" aria-label="Semantic memory results">
        {result.items.map((memory) => (
          <MemoryResultCard key={memory.id} memory={memory} />
        ))}
      </div>
    </>
  );
}

function SemanticSearchProvenance({ result }: { result: SemanticMemorySearchResponse }) {
  const evidenceCount = new Set(result.items.flatMap((item) => item.evidence_ids)).size;

  return (
    <div className="semantic-provenance-strip" aria-label="Semantic search provenance">
      <div>
        <span>Retrieval</span>
        <strong>{memoryProviderLabel(result.provider)}</strong>
        <p>{memoryProviderCopy(result.provider)}</p>
      </div>
      <div>
        <span>Cited rows</span>
        <strong>{result.items.length}</strong>
        <p>{evidenceCount ? `${evidenceCount} evidence reference${evidenceCount === 1 ? "" : "s"} returned.` : "No evidence references returned."}</p>
      </div>
    </div>
  );
}

function MemoryResultCard({ memory }: { memory: SemanticMemoryResult }) {
  return (
    <article className="semantic-result-card">
      <div className="semantic-result-card__header">
        <div>
          <span>{sourceLabel(memory.source_type)}</span>
          <h3>{memory.title}</h3>
        </div>
        <StatusPill label={scoreLabel(memory.score)} tone={memory.score && memory.score > 0 ? "info" : "quiet"} />
      </div>
      <p>{memory.text}</p>
      <dl className="compact-meta compact-meta--two">
        <div>
          <dt>Source ID</dt>
          <dd>{memory.source_id}</dd>
        </div>
        <div>
          <dt>Source links</dt>
          <dd>{memory.source_ids.length ? memory.source_ids.slice(0, 3).join(", ") : "Not reported"}</dd>
        </div>
        <div>
          <dt>When</dt>
          <dd>{formatDateTime(memory.occurred_at)}</dd>
        </div>
        <div>
          <dt>Evidence refs</dt>
          <dd>{memory.evidence_ids.length}</dd>
        </div>
      </dl>
      {memory.match_reasons.length ? (
        <div className="semantic-tag-list" aria-label="Memory tags">
          {memory.match_reasons.slice(0, 8).map((tag) => (
            <span key={tag}>{tag}</span>
          ))}
        </div>
      ) : null}
      <EvidenceRefs ids={memory.evidence_ids} label={`Evidence for ${memory.title}`} />
    </article>
  );
}

function memoryProviderLabel(provider?: string | null): string {
  if (!provider) {
    return "Not reported";
  }
  if (provider === "deterministic_lexical" || provider === "lexical") {
    return "Lexical fallback";
  }
  if (provider === "pgvector") {
    return "Vector retrieval";
  }
  if (provider === "hybrid") {
    return "Hybrid retrieval";
  }
  return sentenceCase(provider);
}

function memoryProviderCopy(provider?: string | null): string {
  if (provider === "pgvector" || provider === "hybrid") {
    return "The backend reports vector-aware memory search for these cited rows.";
  }
  if (provider === "deterministic_lexical" || provider === "lexical") {
    return "Local lexical retrieval is being used; vector memory is not being claimed live.";
  }
  return "Search mode was not reported, so treat this as conservative memory evidence.";
}

function scoreLabel(score?: number | null): string {
  if (typeof score !== "number" || Number.isNaN(score)) {
    return "Score unavailable";
  }
  if (score >= 0 && score <= 1) {
    return `${Math.round(score * 100)} match`;
  }
  return `Rank ${score.toFixed(score >= 10 ? 0 : 2)}`;
}

function sourceLabel(source: string): string {
  return sentenceCase(
    source
      .replace(/^object_memory$/, "object memory")
      .replace(/^diary_entry$/, "diary entry")
      .replace(/^care_note$/, "care note")
      .replace(/^family_message$/, "family message")
      .replace(/^hydration_event$/, "hydration event")
      .replace(/^wellness_check$/, "wellness check")
  );
}

function endpointMessage(error: unknown, fallback: string): { tone?: "error"; title: string; body: string } {
  const status = error instanceof Error && "status" in error ? Number(error.status) : undefined;
  if (isUnavailableEndpoint(status)) {
    return {
      title: "Semantic memory is not ready yet",
      body: fallback
    };
  }

  return {
    tone: "error",
    title: "Memory review failed",
    body: error instanceof Error ? error.message : fallback
  };
}

function statusTone(
  searchResult: SemanticMemorySearchResponse | null,
  reindexResult: SemanticMemoryReindexResponse | null,
  message: { tone?: "error" | "success" } | null
): StatusTone {
  if (message?.tone === "error") {
    return "bad";
  }
  if (searchResult?.items.length || reindexResult?.ok || message?.tone === "success") {
    return "good";
  }
  return "info";
}
