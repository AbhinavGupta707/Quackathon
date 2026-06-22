"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  acknowledgeFamilyMessage,
  createFamilyMessage,
  generateCareNote,
  generateDiary,
  getActivityTimeline,
  getCareNotes,
  getDiary,
  getFamilyMessages,
  isUnavailableEndpoint
} from "@/lib/api";
import { formatDateTime, sentenceCase } from "@/lib/format";
import type {
  ActivityEvent,
  ActivityTimelineResponse,
  CareNote,
  CareNoteAudience,
  CareNotesResponse,
  DiaryResponse,
  FamilyMessage,
  FamilyMessagePriority,
  FamilyMessagesResponse,
  Loadable
} from "@/lib/types";
import { EvidenceRefs } from "./EvidenceRefs";
import { StateBlock } from "./StateBlock";
import { StatusPill, type StatusTone } from "./StatusPill";

const POLL_MS = 20000;

type MessageFormState = {
  body: string;
  expires_at: string;
  priority: FamilyMessagePriority;
  starts_at: string;
  title: string;
  trigger_object_key: string;
  trigger_zone_id: string;
};

const EMPTY_MESSAGE_FORM: MessageFormState = {
  body: "",
  expires_at: "",
  priority: "normal",
  starts_at: "",
  title: "",
  trigger_object_key: "",
  trigger_zone_id: ""
};

export function CaregiverDailyCareClient() {
  const [selectedDate, setSelectedDate] = useState(() => toDateInputValue(new Date()));
  const [timeline, setTimeline] = useState<Loadable<ActivityTimelineResponse>>({ loading: true });
  const [diary, setDiary] = useState<Loadable<DiaryResponse>>({ loading: true });
  const [notes, setNotes] = useState<Loadable<CareNotesResponse>>({ loading: true });
  const [messages, setMessages] = useState<Loadable<FamilyMessagesResponse>>({ loading: true });
  const [audience, setAudience] = useState<CareNoteAudience>("family");
  const [messageForm, setMessageForm] = useState<MessageFormState>(EMPTY_MESSAGE_FORM);
  const [pending, setPending] = useState<"diary" | "note" | "message" | `ack:${string}` | null>(null);
  const [actionMessage, setActionMessage] = useState<{ tone?: "error" | "success"; title: string; body: string } | null>(null);

  const refreshCareData = useCallback(async () => {
    await Promise.all([
      loadInto(setTimeline, () => getActivityTimeline(selectedDate)),
      loadInto(setDiary, () => getDiary(selectedDate)),
      loadInto(setNotes, () => getCareNotes(selectedDate)),
      loadInto(setMessages, () => getFamilyMessages(true))
    ]);
  }, [selectedDate]);

  useEffect(() => {
    void refreshCareData();
    const timer = window.setInterval(() => {
      void refreshCareData();
    }, POLL_MS);

    return () => window.clearInterval(timer);
  }, [refreshCareData]);

  const openMessageCount = useMemo(
    () => (messages.data?.messages ?? []).filter((message) => message.status !== "acknowledged").length,
    [messages.data?.messages]
  );

  async function handleGenerateDiary() {
    setPending("diary");
    setActionMessage(null);
    try {
      const response = await generateDiary(selectedDate);
      setDiary({ data: { date: response.diary.date, diary: response.diary }, loading: false });
      setActionMessage({
        tone: "success",
        title: "Diary generated",
        body: "The daily summary is ready for caregiver review."
      });
    } catch (error) {
      setActionMessage(errorMessage(error, "Diary generation is not available yet."));
    } finally {
      setPending(null);
    }
  }

  async function handleGenerateCareNote() {
    setPending("note");
    setActionMessage(null);
    try {
      const response = await generateCareNote({ audience, date: selectedDate });
      setNotes((previous) => ({
        data: {
          date: response.note.date,
          notes: [response.note, ...(previous.data?.notes ?? []).filter((note) => note.id !== response.note.id)]
        },
        loading: false
      }));
      setActionMessage({
        tone: "success",
        title: "Care note generated",
        body: "The note is ready to review before sharing or acting on it."
      });
    } catch (error) {
      setActionMessage(errorMessage(error, "Care-note generation is not available yet."));
    } finally {
      setPending(null);
    }
  }

  async function handleCreateMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const title = messageForm.title.trim();
    const body = messageForm.body.trim();

    if (!title || !body) {
      setActionMessage({
        title: "Add a title and message",
        body: "Family prompts need a short title and calm message body before saving."
      });
      return;
    }

    setPending("message");
    setActionMessage(null);
    try {
      await createFamilyMessage({
        title,
        body,
        priority: messageForm.priority,
        trigger_object_key: optionalValue(messageForm.trigger_object_key),
        trigger_zone_id: optionalValue(messageForm.trigger_zone_id),
        starts_at: optionalDateTimeIso(messageForm.starts_at),
        expires_at: optionalDateTimeIso(messageForm.expires_at)
      });
      setMessageForm(EMPTY_MESSAGE_FORM);
      setActionMessage({
        tone: "success",
        title: "Family message saved",
        body: "It will appear in patient mode when the backend marks it active."
      });
      await refreshCareData();
    } catch (error) {
      setActionMessage(errorMessage(error, "Family-message creation is not available yet."));
    } finally {
      setPending(null);
    }
  }

  async function handleAcknowledgeMessage(message: FamilyMessage) {
    setPending(`ack:${message.id}`);
    setActionMessage(null);
    try {
      await acknowledgeFamilyMessage(message.id);
      setActionMessage({
        tone: "success",
        title: "Message acknowledged",
        body: "The family prompt state has been updated."
      });
      await refreshCareData();
    } catch (error) {
      setActionMessage(errorMessage(error, "Family-message acknowledgement is not available yet."));
    } finally {
      setPending(null);
    }
  }

  return (
    <section className="caregiver-daily-care" aria-labelledby="daily-care-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Daily Care Review</p>
          <h2 id="daily-care-title">Diary, notes, and family prompts</h2>
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
          <button className="button button--secondary" onClick={() => void refreshCareData()} type="button">
            Refresh care data
          </button>
        </div>
      </div>

      <div className="care-summary-strip" aria-label="Care review summary">
        <CareMetric title="Timeline" value={`${timeline.data?.events.length ?? 0} events`} tone={timeline.error ? "quiet" : timeline.data?.events.length ? "good" : "info"} />
        <CareMetric title="Diary" value={diary.data?.diary ? "Ready" : "No entry"} tone={diary.data?.diary ? "good" : diary.error ? "quiet" : "warn"} />
        <CareMetric title="Care notes" value={`${notes.data?.notes.length ?? 0} notes`} tone={notes.error ? "quiet" : notes.data?.notes.length ? "good" : "info"} />
        <CareMetric title="Family prompts" value={`${openMessageCount} active`} tone={messages.error ? "quiet" : openMessageCount ? "warn" : "info"} />
      </div>

      {actionMessage ? (
        <StateBlock
          tone={actionMessage.tone === "error" ? "error" : actionMessage.tone === "success" ? "success" : "empty"}
          title={actionMessage.title}
          body={actionMessage.body}
        />
      ) : null}

      <div className="care-review-grid">
        <div className="care-review-grid__main">
          <ActivityTimelineCard timeline={timeline} />
          <DiaryReviewCard diary={diary} onGenerate={() => void handleGenerateDiary()} pending={pending === "diary"} />
        </div>

        <div className="care-review-grid__side">
          <CareNotesCard
            audience={audience}
            notes={notes}
            onAudienceChange={setAudience}
            onGenerate={() => void handleGenerateCareNote()}
            pending={pending === "note"}
          />
          <FamilyMessagesCard
            form={messageForm}
            messages={messages}
            onAcknowledge={(message) => void handleAcknowledgeMessage(message)}
            onFormChange={setMessageForm}
            onSubmit={handleCreateMessage}
            pending={pending}
          />
        </div>
      </div>
    </section>
  );
}

function ActivityTimelineCard({ timeline }: { timeline: Loadable<ActivityTimelineResponse> }) {
  return (
    <section className="review-card" aria-labelledby="activity-timeline-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Activity Timeline</p>
          <h2 id="activity-timeline-title">Evidence-backed events</h2>
        </div>
        <StatusPill
          label={timeline.loading ? "Checking" : timeline.error ? "Unavailable" : `${timeline.data?.events.length ?? 0} events`}
          tone={timeline.error ? "quiet" : timeline.data?.events.length ? "good" : "info"}
        />
      </div>

      {timeline.loading && !timeline.data ? (
        <StateBlock tone="loading" title="Loading timeline" body="Checking for today's activity events." />
      ) : timeline.error ? (
        <UnavailableCareState feature="Activity timeline" />
      ) : timeline.data?.events.length ? (
        <ol className="timeline-list">
          {timeline.data.events.map((event) => (
            <TimelineEvent event={event} key={event.id} />
          ))}
        </ol>
      ) : (
        <StateBlock title="No events for this date" body="Events will appear after the backend derives them from live home evidence." />
      )}
    </section>
  );
}

function TimelineEvent({ event }: { event: ActivityEvent }) {
  return (
    <li className="timeline-event">
      <div className="timeline-event__time">{formatDateTime(event.occurred_at)}</div>
      <div className="timeline-event__body">
        <div className="row-heading">
          <strong>{event.title}</strong>
          <StatusPill label={sentenceCase(event.confidence)} tone={confidenceTone(event.confidence)} />
        </div>
        <p>{event.body}</p>
        <dl className="compact-meta compact-meta--two">
          <div>
            <dt>Type</dt>
            <dd>{sentenceCase(event.type)}</dd>
          </div>
          <div>
            <dt>Area</dt>
            <dd>{event.zone_name || event.zone_id || "Unassigned"}</dd>
          </div>
          <div>
            <dt>Source</dt>
            <dd>{event.source}</dd>
          </div>
          <div>
            <dt>Evidence</dt>
            <dd>{event.evidence_ids.length}</dd>
          </div>
        </dl>
        <EvidenceRefs ids={event.evidence_ids} />
      </div>
    </li>
  );
}

function DiaryReviewCard({
  diary,
  onGenerate,
  pending
}: {
  diary: Loadable<DiaryResponse>;
  onGenerate: () => void;
  pending: boolean;
}) {
  const entry = diary.data?.diary ?? null;

  return (
    <section className="review-card" aria-labelledby="diary-review-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Daily Diary</p>
          <h2 id="diary-review-title">Patient-friendly summary</h2>
        </div>
        <button className="button button--secondary" disabled={pending} onClick={onGenerate} type="button">
          {pending ? "Generating" : entry ? "Regenerate diary" : "Generate diary"}
        </button>
      </div>

      {diary.loading && !diary.data ? (
        <StateBlock tone="loading" title="Loading diary" body="Checking for an existing daily diary." />
      ) : diary.error ? (
        <UnavailableCareState feature="Daily diary" />
      ) : entry ? (
        <article className="care-note-card">
          <p>{entry.summary}</p>
          <CareList title="Highlights" items={entry.highlights} empty="No highlights returned." />
          <CareList title="Needs review" items={entry.needs_review} empty="No review items returned." />
          <dl className="compact-meta compact-meta--two">
            <div>
              <dt>Generated</dt>
              <dd>{formatDateTime(entry.generated_at)}</dd>
            </div>
            <div>
              <dt>Source</dt>
              <dd>{entry.source}</dd>
            </div>
          </dl>
          <EvidenceRefs ids={entry.evidence_ids} />
        </article>
      ) : (
        <StateBlock title="No diary yet" body="Generate a diary after activity events are available for this date." />
      )}
    </section>
  );
}

function CareNotesCard({
  audience,
  notes,
  onAudienceChange,
  onGenerate,
  pending
}: {
  audience: CareNoteAudience;
  notes: Loadable<CareNotesResponse>;
  onAudienceChange: (audience: CareNoteAudience) => void;
  onGenerate: () => void;
  pending: boolean;
}) {
  return (
    <section className="review-card" aria-labelledby="care-notes-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Care Notes</p>
          <h2 id="care-notes-title">Low-burden handoff notes</h2>
        </div>
      </div>
      <div className="care-action-row">
        <label>
          Audience
          <select onChange={(event) => onAudienceChange(event.target.value as CareNoteAudience)} value={audience}>
            <option value="family">Family</option>
            <option value="care_home">Care home</option>
          </select>
        </label>
        <button className="button button--secondary" disabled={pending} onClick={onGenerate} type="button">
          {pending ? "Generating" : "Generate note"}
        </button>
      </div>

      {notes.loading && !notes.data ? (
        <StateBlock tone="loading" title="Loading notes" body="Checking generated care notes." />
      ) : notes.error ? (
        <UnavailableCareState feature="Care notes" />
      ) : notes.data?.notes.length ? (
        <div className="care-note-list">
          {notes.data.notes.map((note) => (
            <CareNoteCard key={note.id} note={note} />
          ))}
        </div>
      ) : (
        <StateBlock title="No care notes yet" body="Generate a family or care-home note when the timeline has useful events." />
      )}
    </section>
  );
}

function CareNoteCard({ note }: { note: CareNote }) {
  return (
    <article className="care-note-card">
      <div className="row-heading">
        <strong>{sentenceCase(note.audience)}</strong>
        <StatusPill label={formatDateTime(note.created_at)} tone="quiet" />
      </div>
      <p>{note.summary}</p>
      <CareList title="Notes" items={note.bullets} empty="No note bullets returned." />
      <CareList title="Risks to review" items={note.risks} empty="No risks returned." />
      <CareList title="Follow-ups" items={note.follow_ups} empty="No follow-ups returned." />
      <EvidenceRefs ids={note.evidence_ids} />
    </article>
  );
}

function FamilyMessagesCard({
  form,
  messages,
  onAcknowledge,
  onFormChange,
  onSubmit,
  pending
}: {
  form: MessageFormState;
  messages: Loadable<FamilyMessagesResponse>;
  onAcknowledge: (message: FamilyMessage) => void;
  onFormChange: (form: MessageFormState) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  pending: "diary" | "note" | "message" | `ack:${string}` | null;
}) {
  return (
    <section className="review-card" aria-labelledby="family-messages-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Family Messages</p>
          <h2 id="family-messages-title">Contextual prompts</h2>
        </div>
        <StatusPill
          label={messages.loading ? "Checking" : messages.error ? "Unavailable" : `${messages.data?.messages.length ?? 0} saved`}
          tone={messages.error ? "quiet" : messages.data?.messages.length ? "good" : "info"}
        />
      </div>

      <form className="family-message-form" onSubmit={onSubmit}>
        <label>
          Title
          <input
            onChange={(event) => onFormChange({ ...form, title: event.target.value })}
            placeholder="Tea is ready"
            type="text"
            value={form.title}
          />
        </label>
        <label>
          Priority
          <select
            onChange={(event) => onFormChange({ ...form, priority: event.target.value as FamilyMessagePriority })}
            value={form.priority}
          >
            <option value="low">Low</option>
            <option value="normal">Normal</option>
            <option value="high">High</option>
          </select>
        </label>
        <label className="family-message-form__wide">
          Message
          <textarea
            onChange={(event) => onFormChange({ ...form, body: event.target.value })}
            placeholder="Mum, Sam called and will visit after lunch."
            rows={3}
            value={form.body}
          />
        </label>
        <label>
          Object trigger
          <input
            onChange={(event) => onFormChange({ ...form, trigger_object_key: event.target.value })}
            placeholder="water_bottle"
            type="text"
            value={form.trigger_object_key}
          />
        </label>
        <label>
          Area trigger
          <input
            onChange={(event) => onFormChange({ ...form, trigger_zone_id: event.target.value })}
            placeholder="zone_..."
            type="text"
            value={form.trigger_zone_id}
          />
        </label>
        <label>
          Starts
          <input
            onChange={(event) => onFormChange({ ...form, starts_at: event.target.value })}
            type="datetime-local"
            value={form.starts_at}
          />
        </label>
        <label>
          Expires
          <input
            onChange={(event) => onFormChange({ ...form, expires_at: event.target.value })}
            type="datetime-local"
            value={form.expires_at}
          />
        </label>
        <button className="button button--primary family-message-form__wide" disabled={pending === "message"} type="submit">
          {pending === "message" ? "Saving message" : "Save family message"}
        </button>
      </form>

      {messages.loading && !messages.data ? (
        <StateBlock tone="loading" title="Loading messages" body="Checking family prompt state." />
      ) : messages.error ? (
        <UnavailableCareState feature="Family messages" />
      ) : messages.data?.messages.length ? (
        <div className="family-message-list">
          {messages.data.messages.map((message) => (
            <article className="family-message-row" key={message.id}>
              <div className="row-heading">
                <strong>{message.title}</strong>
                <StatusPill label={sentenceCase(message.status)} tone={messageTone(message)} />
              </div>
              <p>{message.body}</p>
              <dl className="compact-meta compact-meta--two">
                <div>
                  <dt>Priority</dt>
                  <dd>{sentenceCase(message.priority)}</dd>
                </div>
                <div>
                  <dt>Object</dt>
                  <dd>{message.trigger_object_key || "None"}</dd>
                </div>
                <div>
                  <dt>Area</dt>
                  <dd>{message.trigger_zone_id || "None"}</dd>
                </div>
                <div>
                  <dt>Acknowledged</dt>
                  <dd>{formatDateTime(message.acknowledged_at)}</dd>
                </div>
              </dl>
              {message.status !== "acknowledged" ? (
                <button
                  className="button button--secondary"
                  disabled={pending === `ack:${message.id}`}
                  onClick={() => onAcknowledge(message)}
                  type="button"
                >
                  {pending === `ack:${message.id}` ? "Acknowledging" : "Mark acknowledged"}
                </button>
              ) : null}
            </article>
          ))}
        </div>
      ) : (
        <StateBlock title="No family messages yet" body="Save a message to test the patient-facing prompt surface." />
      )}
    </section>
  );
}

function CareList({ empty, items, title }: { empty: string; items: string[]; title: string }) {
  return (
    <div className="care-list-block">
      <strong>{title}</strong>
      {items.length ? (
        <ul className="plain-list">
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="muted">{empty}</p>
      )}
    </div>
  );
}

function CareMetric({ title, value, tone }: { title: string; value: string; tone: StatusTone }) {
  return (
    <div className="connection-tile">
      <span>{title}</span>
      <strong>{value}</strong>
      <StatusPill label={tone === "good" ? "Ready" : tone === "warn" ? "Review" : tone === "quiet" ? "Pending" : "Available"} tone={tone} />
    </div>
  );
}

function UnavailableCareState({ feature }: { feature: string }) {
  return (
    <StateBlock
      title={`${feature} unavailable`}
      body="This daily care endpoint is unavailable. Existing caregiver evidence, ask, and recovery controls remain available."
    />
  );
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

function messageTone(message: FamilyMessage): StatusTone {
  if (message.status === "acknowledged") {
    return "good";
  }
  if (message.priority === "high") {
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

function optionalValue(value: string): string | undefined {
  const trimmed = value.trim();
  return trimmed || undefined;
}

function optionalDateTimeIso(value: string): string | undefined {
  const trimmed = optionalValue(value);
  if (!trimmed) {
    return undefined;
  }
  const parsed = new Date(trimmed);
  if (Number.isNaN(parsed.getTime())) {
    return trimmed;
  }
  return parsed.toISOString();
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
    setter({
      loading: false,
      error: error instanceof Error ? error.message : "Endpoint unavailable."
    });
  }
}

function toDateInputValue(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}
