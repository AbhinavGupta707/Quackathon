"use client";

import { FormEvent, useState } from "react";
import { askQuery } from "@/lib/api";
import { sentenceCase } from "@/lib/format";
import type { QueryResponse } from "@/lib/types";
import { Panel } from "./Panel";
import { StateBlock } from "./StateBlock";
import { StatusPill } from "./StatusPill";

type AskInterfaceProps = {
  sessionId: string;
};

export function AskInterface({ sessionId }: AskInterfaceProps) {
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
      setResult(await askQuery(trimmed, sessionId));
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
            {result.needs_human_verification ? <StatusPill label="Human verification required" tone="warn" /> : null}
          </div>
          <p>{result.answer}</p>
          <dl>
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
              <dd>{result.evidence_observation_ids.join(", ") || "No evidence IDs returned"}</dd>
            </div>
          </dl>
          {result.safety_disclaimer ? <p className="disclaimer">{result.safety_disclaimer}</p> : null}
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
