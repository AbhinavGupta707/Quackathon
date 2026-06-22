"use client";

import { useState } from "react";
import { reviewLatestEnrichment } from "@/lib/api";
import { formatDateTime, formatPercent, sentenceCase } from "@/lib/format";
import type {
  EnrichmentFocus,
  EnrichmentLabelSuggestion,
  EnrichmentLatestResponse,
  EnrichmentProvider,
  LatestEnrichmentResponse,
  LatestObservationResponse,
  Loadable,
  ObservationEnrichment
} from "@/lib/types";
import { EvidenceRefs } from "./EvidenceRefs";
import { StateBlock } from "./StateBlock";
import { StatusPill, type StatusTone } from "./StatusPill";

type EnrichmentInspectorProps = {
  latestObservation: Loadable<LatestObservationResponse>;
  latestEnrichment: Loadable<LatestEnrichmentResponse>;
  onReviewed?: (result: EnrichmentLatestResponse) => void | Promise<void>;
};

const PROVIDERS: Array<{ label: string; value: EnrichmentProvider }> = [
  { label: "Auto", value: "auto" },
  { label: "Fireworks", value: "fireworks" },
  { label: "Gemini", value: "gemini" },
  { label: "Deterministic", value: "deterministic" }
];

const FOCUSES: Array<{ label: string; value: EnrichmentFocus }> = [
  { label: "Labels", value: "label_quality" },
  { label: "Safety", value: "safety" },
  { label: "Scene", value: "scene_context" },
  { label: "All", value: "all" }
];

export function EnrichmentInspector({
  latestObservation,
  latestEnrichment,
  onReviewed
}: EnrichmentInspectorProps) {
  const [provider, setProvider] = useState<EnrichmentProvider>("auto");
  const [focus, setFocus] = useState<EnrichmentFocus>("label_quality");
  const [pending, setPending] = useState(false);
  const [reviewResult, setReviewResult] = useState<EnrichmentLatestResponse | null>(null);
  const [reviewError, setReviewError] = useState<string | null>(null);

  const observation = latestObservation.data?.observation ?? null;
  const observationObjects = observation?.objects ?? [];
  const enrichment = reviewResult?.enrichment ?? latestEnrichment.data?.enrichment ?? null;
  const providerState = reviewResult?.provider_state ?? enrichmentStateFromLatest(enrichment);
  const resultMessage = reviewResult?.message ?? null;
  const suggestions = enrichment?.label_suggestions ?? [];
  const safetyNotes = normalizeNotes(enrichment?.safety_notes);
  const spatialNotes = normalizeNotes(enrichment?.spatial_notes);
  const hasDisagreement = suggestions.some(suggestionHasDisagreement);
  const matchesCurrentObservation = Boolean(enrichment && observation?.id && enrichment.observation_id === observation.id);
  const evidenceIds = enrichment?.evidence_observation_ids?.length
    ? enrichment.evidence_observation_ids
    : enrichment?.observation_id
      ? [enrichment.observation_id]
      : [];

  async function handleReview() {
    setPending(true);
    setReviewError(null);
    setReviewResult(null);

    try {
      const result = await reviewLatestEnrichment({ focus, persist: true, provider });
      setReviewResult(result);
      await onReviewed?.(result);
    } catch (error) {
      setReviewError(error instanceof Error ? error.message : "Enrichment endpoint unavailable.");
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="review-card enrichment-inspector" aria-labelledby="enrichment-inspector-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Multimodal Enrichment</p>
          <h2 id="enrichment-inspector-title">Evidence review</h2>
        </div>
        <StatusPill label={providerStateLabel(providerState)} tone={providerStateTone(providerState)} />
      </div>

      <div className="enrichment-controls" aria-label="Enrichment controls">
        <label>
          <span>Focus</span>
          <select
            aria-label="Enrichment focus"
            onChange={(event) => setFocus(event.target.value as EnrichmentFocus)}
            value={focus}
          >
            {FOCUSES.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Provider</span>
          <select
            aria-label="Enrichment provider"
            onChange={(event) => setProvider(event.target.value as EnrichmentProvider)}
            value={provider}
          >
            {PROVIDERS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <button
          className="button button--primary"
          disabled={pending || latestObservation.loading || !observation}
          onClick={() => void handleReview()}
          type="button"
        >
          {pending ? "Reviewing" : "Review latest observation"}
        </button>
      </div>

      <div className="evidence-layers" aria-label="Evidence layers">
        <section className="evidence-layer evidence-layer--primary">
          <div className="row-heading">
            <h3>Afferens primary</h3>
            <StatusPill label={observation?.modality || "Vision"} tone={observation ? "good" : "quiet"} />
          </div>
          {latestObservation.loading ? (
            <StateBlock tone="loading" title="Checking live evidence" body="Reading the latest synced Afferens observation." />
          ) : latestObservation.error ? (
            <StateBlock tone="error" title="Afferens evidence unavailable" body={latestObservation.error} />
          ) : !observation ? (
            <StateBlock title="No synced live observation" body="Sync live perception before requesting enrichment." />
          ) : (
            <>
              <p>{observation.scene_summary || "Live scene summary unavailable."}</p>
              <div className="object-chip-list" aria-label="Afferens object labels">
                {observationObjects.length > 0 ? (
                  observationObjects.slice(0, 8).map((object) => (
                    <span className="object-chip" key={`${object.object_key}-${object.label}`}>
                      {object.display_name}
                      <small>{formatPercent(object.confidence)}</small>
                    </span>
                  ))
                ) : (
                  <span className="muted">No Afferens object labels in this observation.</span>
                )}
              </div>
              <dl className="compact-meta">
                <div>
                  <dt>Observed</dt>
                  <dd>{formatDateTime(observation.timestamp_utc)}</dd>
                </div>
                <div>
                  <dt>Source</dt>
                  <dd>{observation.source_node_id || "Unknown node"}</dd>
                </div>
                <div>
                  <dt>Observation</dt>
                  <dd>
                    <EvidenceRefs ids={[observation.id]} label="Afferens observation ID" />
                  </dd>
                </div>
              </dl>
            </>
          )}
        </section>

        <section className="evidence-layer">
          <div className="row-heading">
            <h3>Derived review</h3>
            <StatusPill
              label={matchesCurrentObservation ? "Current observation" : enrichment ? "Previous observation" : "No review"}
              tone={matchesCurrentObservation ? "info" : enrichment ? "warn" : "quiet"}
            />
          </div>
          {latestEnrichment.loading && !reviewResult ? (
            <StateBlock tone="loading" title="Checking enrichment" body="Reading the latest derived review, if one exists." />
          ) : latestEnrichment.error && !reviewResult ? (
            <StateBlock
              tone="error"
              title="Enrichment endpoint unavailable"
              body="The backend enrichment route is not active yet. Live sync, memory questions, voice, tasks, and alerts can still be used."
            />
          ) : !enrichment ? (
            <StateBlock
              title="No enrichment saved"
              body="Run a review after a live Afferens observation is synced."
            />
          ) : (
            <EnrichmentResult
              enrichment={enrichment}
              hasDisagreement={hasDisagreement}
              modelRun={reviewResult?.model_run ?? null}
              providerState={providerState}
              evidenceIds={evidenceIds}
              safetyNotes={safetyNotes}
              spatialNotes={spatialNotes}
              suggestions={suggestions}
            />
          )}
        </section>
      </div>

      {resultMessage ? <StateBlock title="Review note" body={resultMessage} tone={reviewResult?.ok ? "success" : "error"} /> : null}
      {reviewError ? (
        <StateBlock
          tone="error"
          title="Review unavailable"
          body={`${reviewError} Live Afferens evidence and recovery flows remain available.`}
        />
      ) : null}
    </section>
  );
}

function EnrichmentResult({
  enrichment,
  evidenceIds,
  hasDisagreement,
  modelRun,
  providerState,
  safetyNotes,
  spatialNotes,
  suggestions
}: {
  enrichment: ObservationEnrichment;
  evidenceIds: string[];
  hasDisagreement: boolean;
  modelRun: EnrichmentLatestResponse["model_run"];
  providerState?: string | null;
  safetyNotes: string[];
  spatialNotes: string[];
  suggestions: EnrichmentLabelSuggestion[];
}) {
  return (
    <div className="enrichment-result">
      <div className="pill-row">
        <StatusPill label={enrichment.source_provider || "provider"} tone="info" />
        <StatusPill label={hasDisagreement ? "Ambiguity found" : "No disagreement flagged"} tone={hasDisagreement ? "warn" : "quiet"} />
        {providerState ? <StatusPill label={providerStateLabel(providerState)} tone={providerStateTone(providerState)} /> : null}
      </div>

      <p>{enrichment.summary || "No enrichment summary returned."}</p>

      {suggestions.length > 0 ? (
        <div className="enrichment-subsection">
          <h3>Label suggestions</h3>
          <div className="suggestion-list">
            {suggestions.map((suggestion, index) => (
              <article className="suggestion-card" key={suggestionKey(suggestion, index)}>
                <div className="row-heading">
                  <strong>{suggestionTitle(suggestion)}</strong>
                  <StatusPill
                    label={suggestionHasDisagreement(suggestion) ? "Check label" : "Review"}
                    tone={suggestionHasDisagreement(suggestion) ? "warn" : "quiet"}
                  />
                </div>
                <p>{suggestionDetail(suggestion)}</p>
              </article>
            ))}
          </div>
        </div>
      ) : null}

      <NoteList title="Safety notes" notes={safetyNotes} empty="No safety notes returned." />
      <NoteList title="Spatial notes" notes={spatialNotes} empty="No spatial notes returned." />

      <dl className="compact-meta compact-meta--two">
        <div>
          <dt>Model</dt>
          <dd>{modelRun?.model || enrichment.source_model || "Not reported"}</dd>
        </div>
        <div>
          <dt>Run state</dt>
          <dd>{modelRun?.state ? sentenceCase(modelRun.state) : "Latest saved review"}</dd>
        </div>
        <div>
          <dt>Latency</dt>
          <dd>{typeof modelRun?.latency_ms === "number" ? `${modelRun.latency_ms} ms` : "Not reported"}</dd>
        </div>
        <div>
          <dt>Created</dt>
          <dd>{formatDateTime(enrichment.created_at)}</dd>
        </div>
      </dl>

      {modelRun?.error_message ? (
        <StateBlock tone="error" title="Model note" body={modelRun.error_message} />
      ) : null}

      {evidenceIds.length > 0 ? (
        <div className="enrichment-evidence">
          <span>Evidence refs</span>
          <EvidenceRefs ids={evidenceIds} label="Enrichment evidence observation IDs" />
        </div>
      ) : null}
    </div>
  );
}

function NoteList({ empty, notes, title }: { empty: string; notes: string[]; title: string }) {
  return (
    <div className="enrichment-subsection">
      <h3>{title}</h3>
      {notes.length > 0 ? (
        <ul className="plain-list">
          {notes.map((note, index) => (
            <li key={`${title}-${index}`}>{note}</li>
          ))}
        </ul>
      ) : (
        <p className="muted">{empty}</p>
      )}
    </div>
  );
}

function normalizeNotes(value: ObservationEnrichment["safety_notes"]): string[] {
  if (Array.isArray(value)) {
    return value.filter(Boolean);
  }
  if (typeof value === "string" && value.trim()) {
    return [value.trim()];
  }
  return [];
}

function suggestionKey(suggestion: EnrichmentLabelSuggestion, index: number): string {
  if (typeof suggestion === "string") {
    return `${suggestion}-${index}`;
  }
  return `${suggestion.object_key || suggestion.suggested_label || suggestion.label || "suggestion"}-${index}`;
}

function suggestionTitle(suggestion: EnrichmentLabelSuggestion): string {
  if (typeof suggestion === "string") {
    return suggestion;
  }

  const suggested = suggestion.suggested_label || suggestion.label || suggestion.object_key;
  const original = suggestion.original_label || suggestion.afferens_label;

  if (original && suggested && original.toLowerCase() !== suggested.toLowerCase()) {
    return `${original} -> ${suggested}`;
  }

  return suggested || original || "Label review";
}

function suggestionDetail(suggestion: EnrichmentLabelSuggestion): string {
  if (typeof suggestion === "string") {
    return "Review this derived suggestion against the live Afferens evidence.";
  }

  const notes = [
    suggestion.disagreement,
    suggestion.ambiguity,
    suggestion.rationale,
    suggestion.reason,
    typeof suggestion.confidence === "number" ? `Confidence ${formatPercent(suggestion.confidence)}.` : null
  ].filter(Boolean);

  return notes.join(" ") || "No additional rationale returned.";
}

function suggestionHasDisagreement(suggestion: EnrichmentLabelSuggestion): boolean {
  if (typeof suggestion === "string") {
    return /ambiguous|uncertain|instead|versus| vs |disagree/i.test(suggestion);
  }

  const original = suggestion.original_label || suggestion.afferens_label;
  const suggested = suggestion.suggested_label || suggestion.label;

  return Boolean(
    suggestion.disagreement ||
      suggestion.ambiguity ||
      (original && suggested && original.toLowerCase() !== suggested.toLowerCase())
  );
}

function enrichmentStateFromLatest(enrichment: ObservationEnrichment | null): string | null {
  return enrichment ? "used" : null;
}

function providerStateLabel(state?: string | null): string {
  if (!state) {
    return "Not reviewed";
  }
  return sentenceCase(state);
}

function providerStateTone(state?: string | null): StatusTone {
  if (state === "used") {
    return "good";
  }
  if (state === "fallback" || state === "skipped") {
    return "warn";
  }
  if (state === "unavailable") {
    return "bad";
  }
  return "quiet";
}
