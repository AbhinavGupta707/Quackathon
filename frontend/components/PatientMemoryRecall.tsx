"use client";

import { FormEvent, useMemo, useState } from "react";
import { askSemanticMemory, isUnavailableEndpoint } from "@/lib/api";
import type { MemoryAskResponse } from "@/lib/types";
import { StateBlock } from "./StateBlock";
import { StatusPill } from "./StatusPill";

const MEMORY_PROMPTS = [
  "What happened this morning?",
  "What did I do today?",
  "Did I leave anything important out?",
  "What should I remember from today?"
];

export function PatientMemoryRecall() {
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState<MemoryAskResponse | null>(null);
  const [askedQuestion, setAskedQuestion] = useState("");
  const [message, setMessage] = useState<{ tone?: "error"; title: string; body: string } | null>(null);
  const [loading, setLoading] = useState(false);

  const suggestedPrompt = useMemo(() => MEMORY_PROMPTS[0], []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = query.trim() || suggestedPrompt;
    setQuery(trimmed);
    setAskedQuestion(trimmed);
    setAnswer(null);
    setMessage(null);
    setLoading(true);

    try {
      const response = await askSemanticMemory(trimmed);
      setAnswer(response);
    } catch (error) {
      const status = error instanceof Error && "status" in error ? Number(error.status) : undefined;
      if (isUnavailableEndpoint(status)) {
        setMessage({
          title: "More memory help is not ready yet",
          body: "I can still help find things. Broader day and routine questions will work when this memory feature is available."
        });
      } else {
        setMessage({
          tone: "error",
          title: "I could not answer that yet",
          body: error instanceof Error ? error.message : "Please try again in a moment."
        });
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="patient-panel patient-recall-card" aria-labelledby="patient-recall-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Remember with me</p>
          <h2 id="patient-recall-title">Ask about today</h2>
        </div>
        <StatusPill label={answer ? confidenceLabel(answer.confidence) : "Gentle recall"} tone={answer ? confidenceTone(answer.confidence) : "info"} />
      </div>

      <form className="memory-recall-form" onSubmit={handleSubmit}>
        <label htmlFor="patient-memory-question">Question</label>
        <div className="memory-recall-form__controls">
          <input
            id="patient-memory-question"
            onChange={(event) => setQuery(event.target.value)}
            placeholder={suggestedPrompt}
            type="text"
            value={query}
          />
          <button className="button button--primary" disabled={loading} type="submit">
            {loading ? "Remembering" : "Ask"}
          </button>
        </div>
      </form>

      <div className="memory-prompt-row" aria-label="Suggested memory questions">
        {MEMORY_PROMPTS.map((prompt) => (
          <button className="memory-prompt" key={prompt} onClick={() => setQuery(prompt)} type="button">
            {prompt}
          </button>
        ))}
      </div>

      {message ? (
        <StateBlock tone={message.tone === "error" ? "error" : "empty"} title={message.title} body={message.body} />
      ) : answer ? (
        <div className="patient-memory-answer">
          <p className="muted">{askedQuestion}</p>
          <strong>{answer.answer}</strong>
          <span>
            {answer.evidence_ids.length
              ? `Based on ${answer.evidence_ids.length} remembered note${answer.evidence_ids.length === 1 ? "" : "s"}.`
              : "I do not have enough remembered notes for this yet."}
          </span>
          <span>{patientProviderPhrase(answer.provider, answer.used_memory)}</span>
          {answer.needs_human_verification ? <span>Please check important details with a caregiver.</span> : null}
        </div>
      ) : (
        <StateBlock
          title="Ask a broader memory question"
          body="You can ask about the morning, today, family notes, or anything I may have seen in recent home notes."
        />
      )}
    </section>
  );
}

function confidenceLabel(confidence: MemoryAskResponse["confidence"]): string {
  if (confidence === "high") {
    return "Clear memory";
  }
  if (confidence === "medium") {
    return "Some memory";
  }
  return "Please verify";
}

function confidenceTone(confidence: MemoryAskResponse["confidence"]) {
  if (confidence === "high") {
    return "good" as const;
  }
  if (confidence === "medium") {
    return "info" as const;
  }
  return "warn" as const;
}

function patientProviderPhrase(provider?: string | null, usedMemory?: boolean): string {
  if (!usedMemory) {
    return "I did not find enough cited home memory for this answer.";
  }
  if (provider === "fireworks") {
    return "A helper model made the wording clearer after home memory was found.";
  }
  return "This answer used local home memory wording.";
}
