"use client";

import { FormEvent, useState } from "react";
import { askQuery } from "@/lib/api";
import { sentenceCase } from "@/lib/format";
import type { QueryResponse } from "@/lib/types";
import { EvidenceRefs } from "./EvidenceRefs";
import { Panel } from "./Panel";
import { StateBlock } from "./StateBlock";
import { StatusPill } from "./StatusPill";

type AskInterfaceProps = {
  sessionId: string;
  onAnswered?: () => void;
};

export function AskInterface({ sessionId, onAnswered }: AskInterfaceProps) {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmed = query.trim();
    if (!trimmed) {
      setError("Enter a question before asking live memory.");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await askQuery(trimmed, sessionId);
      setResult(response);
      onAnswered?.();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Query endpoint unavailable.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Panel title="Ask Memory Guardian" eyebrow="Evidence-Backed Query">
      <form className="ask-form" onSubmit={onSubmit}>
        <label htmlFor="guardian-query">Question</label>
        <div className="ask-form__controls">
          <input
            id="guardian-query"
            name="query"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Where are my keys?"
            type="text"
            value={query}
          />
          <button className="button button--primary" disabled={loading} type="submit">
            {loading ? "Asking" : "Ask"}
          </button>
        </div>
      </form>

      {error ? <StateBlock tone="error" title="Query unavailable" body={error} /> : null}

      {result ? (
        <div className="answer">
          <div className="row-heading">
            <StatusPill label={sentenceCase(result.confidence)} tone={result.confidence === "high" ? "good" : "warn"} />
            <StatusPill label={sentenceCase(result.intent)} tone="info" />
            <StatusPill label={result.used_current_perception ? "Current perception" : "No current perception"} tone={result.used_current_perception ? "good" : "quiet"} />
            <StatusPill label={result.used_memory ? "Memory used" : "Memory not used"} tone={result.used_memory ? "info" : "quiet"} />
            {result.needs_human_verification ? <StatusPill label="Human verification required" tone="warn" /> : null}
          </div>
          <p>{result.answer}</p>
          <dl className="answer-meta">
            <div>
              <dt>Current perception</dt>
              <dd>{result.used_current_perception ? "Used" : "Not used"}</dd>
            </div>
            <div>
              <dt>Memory</dt>
              <dd>{result.used_memory ? "Used" : "Not used"}</dd>
            </div>
            <div>
              <dt>Evidence</dt>
              <dd>
                <EvidenceRefs ids={result.evidence_observation_ids} label="Query evidence observations" />
              </dd>
            </div>
            <div>
              <dt>Task</dt>
              <dd>{result.task_id || "No recovery task returned"}</dd>
            </div>
          </dl>
          <p className="disclaimer">
            {result.safety_disclaimer ||
              "This is an assistive prototype. Please verify important items in person."}
          </p>
        </div>
      ) : (
        <StateBlock
          title="No answer yet"
          body="Answers should cite live current perception or durable memory evidence returned by the backend."
        />
      )}
    </Panel>
  );
}
