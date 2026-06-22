"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  acknowledgeWellnessCheck,
  generateWellnessChecks,
  getHydrationSummary,
  getWellnessChecks,
  isUnavailableEndpoint,
  recordHydrationEvent
} from "@/lib/api";
import { formatDateTime, sentenceCase } from "@/lib/format";
import type {
  HydrationSummaryResponse,
  Loadable,
  WellnessCheck,
  WellnessChecksResponse,
  WellnessConfidence
} from "@/lib/types";
import { EvidenceRefs } from "./EvidenceRefs";
import { StateBlock } from "./StateBlock";
import { StatusPill, type StatusTone } from "./StatusPill";

const POLL_MS = 20000;

type HydrationFormState = {
  confidence: WellnessConfidence;
  note: string;
};

const EMPTY_HYDRATION_FORM: HydrationFormState = {
  confidence: "medium",
  note: ""
};

export function CaregiverWellnessClient() {
  const [selectedDate, setSelectedDate] = useState(() => toDateInputValue(new Date()));
  const [hydration, setHydration] = useState<Loadable<HydrationSummaryResponse>>({ loading: true });
  const [checks, setChecks] = useState<Loadable<WellnessChecksResponse>>({ loading: true });
  const [hydrationForm, setHydrationForm] = useState<HydrationFormState>(EMPTY_HYDRATION_FORM);
  const [ackNotes, setAckNotes] = useState<Record<string, string>>({});
  const [pending, setPending] = useState<"generate" | "hydration" | `ack:${string}` | null>(null);
  const [actionMessage, setActionMessage] = useState<{
    tone?: "error" | "success";
    title: string;
    body: string;
  } | null>(null);

  const refreshWellnessData = useCallback(async () => {
    await Promise.all([
      loadInto(setHydration, () => getHydrationSummary(selectedDate)),
      loadInto(setChecks, () => getWellnessChecks(selectedDate))
    ]);
  }, [selectedDate]);

  useEffect(() => {
    void refreshWellnessData();
    const timer = window.setInterval(() => {
      void refreshWellnessData();
    }, POLL_MS);

    return () => window.clearInterval(timer);
  }, [refreshWellnessData]);

  const openChecks = useMemo(
    () => (checks.data?.checks ?? []).filter((check) => check.status === "open"),
    [checks.data?.checks]
  );
  const summary = hydration.data?.summary ?? null;

  async function handleGenerateChecks() {
    setPending("generate");
    setActionMessage(null);
    try {
      const response = await generateWellnessChecks(selectedDate);
      setChecks({ data: { date: selectedDate, checks: response.checks }, loading: false });
      setActionMessage({
        tone: "success",
        title: "Wellness checks generated",
        body: "Review the candidates below before deciding what to do next."
      });
      await refreshWellnessData();
    } catch (error) {
      setActionMessage(errorMessage(error, "Wellness-check generation is not available yet."));
    } finally {
      setPending(null);
    }
  }

  async function handleRecordHydration(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending("hydration");
    setActionMessage(null);
    try {
      await recordHydrationEvent({
        type: "caregiver_reported",
        occurred_at: new Date().toISOString(),
        confidence: hydrationForm.confidence,
        metadata: {
          source: "caregiver_review",
          note: hydrationForm.note.trim() || undefined
        }
      });
      setHydrationForm(EMPTY_HYDRATION_FORM);
      setActionMessage({
        tone: "success",
        title: "Hydration event recorded",
        body: "The caregiver-reported event is now part of today's hydration review."
      });
      await refreshWellnessData();
    } catch (error) {
      setActionMessage(errorMessage(error, "Caregiver-reported hydration is not available yet."));
    } finally {
      setPending(null);
    }
  }

  async function handleAcknowledgeCheck(check: WellnessCheck) {
    setPending(`ack:${check.id}`);
    setActionMessage(null);
    try {
      await acknowledgeWellnessCheck(check.id, {
        acknowledged_by: "caregiver",
        note: ackNotes[check.id]
      });
      setAckNotes((previous) => ({ ...previous, [check.id]: "" }));
      setActionMessage({
        tone: "success",
        title: "Wellness check acknowledged",
        body: "The check remains available in the review history with its evidence and uncertainty."
      });
      await refreshWellnessData();
    } catch (error) {
      setActionMessage(errorMessage(error, "Wellness-check acknowledgement is not available yet."));
    } finally {
      setPending(null);
    }
  }

  const endpointUnavailable = hydration.error && checks.error;

  return (
    <section className="caregiver-wellness" aria-labelledby="wellness-review-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Hydration And Wellness</p>
          <h2 id="wellness-review-title">Candidate checks for caregiver review</h2>
        </div>
        <div className="date-control">
          <label>
            Review date
            <input
              onChange={(event) => setSelectedDate(event.target.value)}
              type="date"
              value={selectedDate}
            />
          </label>
          <button className="button button--secondary" onClick={() => void refreshWellnessData()} type="button">
            Refresh wellness
          </button>
        </div>
      </div>

      <div className="care-summary-strip wellness-summary-strip" aria-label="Wellness review summary">
        <WellnessMetric
          title="Hydration"
          value={summary ? sentenceCase(summary.status) : hydration.loading ? "Checking" : "Unavailable"}
          tone={hydrationTone(summary?.status, hydration.error)}
        />
        <WellnessMetric
          title="Drink context"
          value={summary ? String(summary.water_events) : "Unknown"}
          tone={summary?.water_events ? "good" : hydration.error ? "quiet" : "info"}
        />
        <WellnessMetric
          title="Open checks"
          value={checks.error ? "Unavailable" : String(openChecks.length)}
          tone={checks.error ? "quiet" : openChecks.length ? "warn" : "good"}
        />
        <WellnessMetric
          title="Latest context"
          value={formatDateTime(summary?.latest_event_at)}
          tone={summary?.latest_event_at ? "info" : "quiet"}
        />
      </div>

      {actionMessage ? (
        <StateBlock
          tone={actionMessage.tone === "error" ? "error" : actionMessage.tone === "success" ? "success" : "empty"}
          title={actionMessage.title}
          body={actionMessage.body}
        />
      ) : null}

      {endpointUnavailable ? (
        <StateBlock
          title="Wellness endpoints unavailable"
          body="Hydration and wellness review will appear here when the backend endpoints are available. The existing caregiver evidence queue still works."
        />
      ) : null}

      <div className="wellness-review-grid">
        <HydrationReviewCard
          form={hydrationForm}
          hydration={hydration}
          onFormChange={setHydrationForm}
          onSubmit={handleRecordHydration}
          pending={pending === "hydration"}
        />
        <WellnessChecksCard
          ackNotes={ackNotes}
          checks={checks}
          onAckNoteChange={(checkId, note) => setAckNotes((previous) => ({ ...previous, [checkId]: note }))}
          onAcknowledge={(check) => void handleAcknowledgeCheck(check)}
          onGenerate={() => void handleGenerateChecks()}
          pending={pending}
        />
      </div>
    </section>
  );
}

function HydrationReviewCard({
  form,
  hydration,
  onFormChange,
  onSubmit,
  pending
}: {
  form: HydrationFormState;
  hydration: Loadable<HydrationSummaryResponse>;
  onFormChange: (form: HydrationFormState) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  pending: boolean;
}) {
  const summary = hydration.data?.summary ?? null;

  return (
    <section className="review-card" aria-labelledby="hydration-review-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Hydration</p>
          <h2 id="hydration-review-title">Hydration review context</h2>
        </div>
        <StatusPill
          label={hydration.loading ? "Checking" : summary ? sentenceCase(summary.status) : "Unavailable"}
          tone={hydrationTone(summary?.status, hydration.error)}
        />
      </div>

      {hydration.loading && !hydration.data ? (
        <StateBlock tone="loading" title="Loading hydration summary" body="Checking drink-action and caregiver-confirmed context." />
      ) : hydration.error ? (
        <UnavailableWellnessState feature="Hydration summary" />
      ) : summary ? (
        <div className="wellness-detail">
          <p>{summary.message || "No hydration message returned."}</p>
          <dl className="compact-meta compact-meta--two">
            <div>
              <dt>Drink context</dt>
              <dd>{summary.water_events}</dd>
            </div>
            <div>
              <dt>Latest event</dt>
              <dd>{formatDateTime(summary.latest_event_at)}</dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>{sentenceCase(summary.status)}</dd>
            </div>
            <div>
              <dt>Evidence count</dt>
              <dd>{summary.evidence_ids.length}</dd>
            </div>
          </dl>
          <p className="muted">Bottle, cup, or water visibility is context only. It is not confirmed hydration intake.</p>
          <EvidenceRefs ids={summary.evidence_ids} />
          {summary.events.length ? (
            <div className="wellness-event-list">
              {summary.events.slice(0, 4).map((event) => (
                <article className="wellness-event-row" key={event.id}>
                  <div className="row-heading">
                    <strong>{sentenceCase(event.type)}</strong>
                    <StatusPill label={sentenceCase(event.confidence)} tone={confidenceTone(event.confidence)} />
                  </div>
                  <p>
                    {formatDateTime(event.occurred_at)}
                    {event.zone_name ? ` in ${event.zone_name}` : ""}
                  </p>
                  <EvidenceRefs ids={event.evidence_ids} />
                </article>
              ))}
            </div>
          ) : null}
        </div>
      ) : (
        <StateBlock title="No hydration summary" body="Generate wellness checks or record a caregiver report after live evidence is available." />
      )}

      <form className="wellness-form" onSubmit={onSubmit}>
        <label>
          Caregiver confidence
          <select
            onChange={(event) =>
              onFormChange({ ...form, confidence: event.target.value as WellnessConfidence })
            }
            value={form.confidence}
          >
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </select>
        </label>
        <label>
          Note
          <input
            onChange={(event) => onFormChange({ ...form, note: event.target.value })}
            placeholder="Offered water after lunch"
            type="text"
            value={form.note}
          />
        </label>
        <button className="button button--secondary wellness-form__wide" disabled={pending} type="submit">
          {pending ? "Recording" : "Record caregiver hydration"}
        </button>
      </form>
    </section>
  );
}

function WellnessChecksCard({
  ackNotes,
  checks,
  onAckNoteChange,
  onAcknowledge,
  onGenerate,
  pending
}: {
  ackNotes: Record<string, string>;
  checks: Loadable<WellnessChecksResponse>;
  onAckNoteChange: (checkId: string, note: string) => void;
  onAcknowledge: (check: WellnessCheck) => void;
  onGenerate: () => void;
  pending: "generate" | "hydration" | `ack:${string}` | null;
}) {
  const checkList = checks.data?.checks ?? [];

  return (
    <section className="review-card" aria-labelledby="wellness-checks-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Wellness Checks</p>
          <h2 id="wellness-checks-title">Review and acknowledge</h2>
        </div>
        <button className="button button--secondary" disabled={pending === "generate"} onClick={onGenerate} type="button">
          {pending === "generate" ? "Generating" : "Generate checks"}
        </button>
      </div>

      {checks.loading && !checks.data ? (
        <StateBlock tone="loading" title="Loading wellness checks" body="Checking for open caregiver review items." />
      ) : checks.error ? (
        <UnavailableWellnessState feature="Wellness checks" />
      ) : checkList.length ? (
        <div className="wellness-check-list">
          {checkList.map((check) => (
            <article className="wellness-check-row" key={check.id}>
              <div className="row-heading">
                <strong>{check.title}</strong>
                <StatusPill label={sentenceCase(check.status)} tone={checkStatusTone(check)} />
              </div>
              <p>{check.body}</p>
              <dl className="compact-meta compact-meta--two">
                <div>
                  <dt>Type</dt>
                  <dd>{sentenceCase(check.type)}</dd>
                </div>
                <div>
                  <dt>Severity</dt>
                  <dd>{sentenceCase(check.severity)}</dd>
                </div>
                <div>
                  <dt>Confidence</dt>
                  <dd>{sentenceCase(check.confidence)}</dd>
                </div>
                <div>
                  <dt>Area</dt>
                  <dd>{check.zone_name || check.zone_id || "Unassigned"}</dd>
                </div>
                <div>
                  <dt>Occurred</dt>
                  <dd>{formatDateTime(check.occurred_at)}</dd>
                </div>
                <div>
                  <dt>Acknowledged</dt>
                  <dd>{formatDateTime(check.acknowledged_at)}</dd>
                </div>
              </dl>
              <EvidenceRefs ids={check.evidence_ids} />
              {check.status === "open" ? (
                <div className="wellness-ack-row">
                  <label>
                    Acknowledgement note
                    <input
                      onChange={(event) => onAckNoteChange(check.id, event.target.value)}
                      placeholder="Checked in by phone"
                      type="text"
                      value={ackNotes[check.id] ?? ""}
                    />
                  </label>
                  <button
                    className="button button--primary"
                    disabled={pending === `ack:${check.id}`}
                    onClick={() => onAcknowledge(check)}
                    type="button"
                  >
                    {pending === `ack:${check.id}` ? "Acknowledging" : "Mark checked"}
                  </button>
                </div>
              ) : null}
            </article>
          ))}
        </div>
      ) : (
        <StateBlock
          title="No wellness checks for this date"
          body="Generate checks after live activity evidence is available, or record caregiver-reported hydration above."
        />
      )}
    </section>
  );
}

function WellnessMetric({ title, value, tone }: { title: string; value: string; tone: StatusTone }) {
  return (
    <div className="connection-tile">
      <span>{title}</span>
      <strong>{value}</strong>
      <StatusPill label={tone === "good" ? "Ready" : tone === "warn" ? "Review" : tone === "quiet" ? "Pending" : "Available"} tone={tone} />
    </div>
  );
}

function UnavailableWellnessState({ feature }: { feature: string }) {
  return (
    <StateBlock
      title={`${feature} unavailable`}
      body="This wellness endpoint is unavailable. Other caregiver review panels remain available."
    />
  );
}

function hydrationTone(status?: string, error?: string): StatusTone {
  if (error) {
    return "quiet";
  }
  if (status === "okay") {
    return "good";
  }
  if (status === "consider_prompting") {
    return "warn";
  }
  return "info";
}

function confidenceTone(confidence: string): StatusTone {
  if (confidence === "high") {
    return "good";
  }
  if (confidence === "medium") {
    return "info";
  }
  return "warn";
}

function checkStatusTone(check: WellnessCheck): StatusTone {
  if (check.status === "acknowledged" || check.status === "dismissed") {
    return "good";
  }
  if (check.severity === "high" || check.severity === "medium") {
    return "warn";
  }
  return "info";
}

function errorMessage(error: unknown, fallback: string): { tone: "error" | undefined; title: string; body: string } {
  const status = error instanceof Error && "status" in error ? Number(error.status) : undefined;
  if (isUnavailableEndpoint(status)) {
    return {
      tone: undefined,
      title: "Feature not ready yet",
      body: fallback
    };
  }

  return {
    tone: "error",
    title: "Action failed",
    body: error instanceof Error ? error.message : fallback
  };
}

async function loadInto<T>(
  setter: (next: Loadable<T> | ((previous: Loadable<T>) => Loadable<T>)) => void,
  loader: () => Promise<T>
) {
  setter((previous) => ({ ...previous, loading: true, error: undefined }));

  try {
    const data = await loader();
    setter({ data, loading: false });
  } catch (error) {
    const status = error instanceof Error && "status" in error ? Number(error.status) : undefined;
    setter({
      loading: false,
      error: isUnavailableEndpoint(status)
        ? "Wellness endpoint unavailable."
        : error instanceof Error
          ? error.message
          : "Endpoint unavailable."
    });
  }
}

function toDateInputValue(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}
