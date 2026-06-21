"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  acknowledgeAlert,
  askQuery,
  getAfferensStatus,
  getAlerts,
  getHealth,
  getLatestObservation,
  getObjects,
  getTasks,
  resolveTask,
  syncPerception,
  verifyTask
} from "@/lib/api";
import { formatDateTime, formatPercent, sentenceCase } from "@/lib/format";
import type {
  AfferensStatus,
  AlertAckResponse,
  AlertsResponse,
  HealthResponse,
  LatestObservationResponse,
  Loadable,
  ObjectsResponse,
  QueryResponse,
  SyncResponse,
  TaskResolveResponse,
  TasksResponse,
  TaskVerifyResponse
} from "@/lib/types";
import { EvidenceRefs } from "@/components/EvidenceRefs";
import { StateBlock } from "@/components/StateBlock";
import { StatusPill, type StatusTone } from "@/components/StatusPill";

const POLL_MS = 10000;

export default function Home() {
  const sessionId = useMemo(() => "browser-session", []);
  const [health, setHealth] = useState<Loadable<HealthResponse>>({ loading: true });
  const [afferens, setAfferens] = useState<Loadable<AfferensStatus>>({ loading: true });
  const [latestObservation, setLatestObservation] = useState<Loadable<LatestObservationResponse>>({ loading: true });
  const [objects, setObjects] = useState<Loadable<ObjectsResponse>>({ loading: true });
  const [tasks, setTasks] = useState<Loadable<TasksResponse>>({ loading: true });
  const [alerts, setAlerts] = useState<Loadable<AlertsResponse>>({ loading: true });
  const [syncPending, setSyncPending] = useState(false);
  const [syncError, setSyncError] = useState<string | undefined>();
  const [syncResult, setSyncResult] = useState<SyncResponse | null>(null);
  const [query, setQuery] = useState("");
  const [queryResult, setQueryResult] = useState<QueryResponse | null>(null);
  const [queryError, setQueryError] = useState<string | null>(null);
  const [queryPending, setQueryPending] = useState(false);

  const rememberedObjects = objects.data?.objects ?? [];
  const currentObservation = latestObservation.data?.observation ?? null;
  const currentObjects = currentObservation?.objects ?? [];
  const openTasks = (tasks.data?.tasks ?? []).filter(
    (task) => !["verified_resolved", "dismissed"].includes(task.state)
  );
  const suggestedObject = currentObjects[0]?.display_name || rememberedObjects[0]?.display_name || "bottle";
  const suggestedQuery = `Where is the ${suggestedObject}?`;

  const refreshAll = useCallback(async () => {
    await Promise.all([
      loadInto(setHealth, getHealth),
      loadInto(setAfferens, getAfferensStatus),
      loadInto(setLatestObservation, getLatestObservation),
      loadInto(setObjects, getObjects),
      loadInto(setTasks, getTasks),
      loadInto(setAlerts, getAlerts)
    ]);
  }, []);

  useEffect(() => {
    void refreshAll();
    const timer = window.setInterval(() => {
      void refreshAll();
    }, POLL_MS);

    return () => window.clearInterval(timer);
  }, [refreshAll]);

  async function handleSync() {
    setSyncPending(true);
    setSyncError(undefined);
    setSyncResult(null);

    try {
      const result = await syncPerception();
      setSyncResult(result);
      await refreshAll();
    } catch (error) {
      setSyncError(error instanceof Error ? error.message : "Live perception sync failed.");
    } finally {
      setSyncPending(false);
    }
  }

  async function handleAsk(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmed = query.trim() || suggestedQuery;
    setQuery(trimmed);
    setQueryPending(true);
    setQueryError(null);
    setQueryResult(null);

    try {
      const result = await askQuery(trimmed, sessionId);
      setQueryResult(result);
      await refreshAll();
    } catch (error) {
      setQueryError(error instanceof Error ? error.message : "Query endpoint unavailable.");
    } finally {
      setQueryPending(false);
    }
  }

  return (
    <main className="test-console">
      <section className="hero-band" aria-labelledby="app-title">
        <div className="hero-copy">
          <p className="eyebrow">Afferens Memory Guardian</p>
          <h1 id="app-title">Live Test Console</h1>
          <p>
            Start the phone node, sync one live camera event, then ask where an object was seen.
          </p>
        </div>
        <div className="ready-card" aria-label="Current connection summary">
          <StatusPill label={connectionLabel(health, afferens)} tone={connectionTone(health, afferens)} />
          <strong>{afferens.data?.latest_event_id || "No live event yet"}</strong>
          <span>{afferens.data?.message || health.error || "Checking local services."}</span>
        </div>
      </section>

      <section className="connection-strip" aria-label="Connection checks">
        <ConnectionTile title="Backend" value={backendLabel(health)} tone={backendTone(health)} detail="localhost:8010" />
        <ConnectionTile title="Afferens Node" value={afferensLabel(afferens)} tone={afferensTone(afferens)} detail={afferens.data?.source_node_id || "phone not live yet"} />
        <ConnectionTile title="Objects Seen" value={String(rememberedObjects.length)} tone={rememberedObjects.length ? "good" : "quiet"} detail="saved in memory" />
        <ConnectionTile title="Tasks" value={String(openTasks.length)} tone={openTasks.length ? "warn" : "quiet"} detail="recovery or safety" />
      </section>

      <section className="flow-grid" aria-label="Live test workflow">
        <article className="flow-card">
          <span className="step-number">1</span>
          <div className="flow-card__body">
            <h2>Phone Node</h2>
            <p>On your phone, keep Afferens on and pointed at one clear object.</p>
            <div className="check-row">
              <StatusPill label={afferens.data?.state ? sentenceCase(afferens.data.state) : "Checking"} tone={afferensTone(afferens)} />
              <span>{afferens.data?.latest_event_id || "Waiting for first event"}</span>
            </div>
          </div>
        </article>

        <article className="flow-card flow-card--primary">
          <span className="step-number">2</span>
          <div className="flow-card__body">
            <h2>Sync Camera</h2>
            <p>Pull the latest Afferens Vision event into our memory store.</p>
            <button className="button button--primary" type="button" onClick={handleSync} disabled={syncPending}>
              {syncPending ? "Syncing live camera" : "Sync Live Perception"}
            </button>
            {syncResult ? (
              <StateBlock
                tone={syncResult.ok ? "success" : "error"}
                title={syncResult.ok ? "Sync worked" : "Sync had a problem"}
                body={`${syncResult.observations?.length ?? 0} observation, ${
                  syncResult.objects_updated?.length ?? 0
                } object update, ${syncResult.tasks_created?.length ?? 0} task, ${
                  syncResult.alerts_created?.length ?? 0
                } alert.`}
              />
            ) : null}
            {syncError ? <StateBlock tone="error" title="Sync failed" body={syncError} /> : null}
          </div>
        </article>

        <article className="flow-card">
          <span className="step-number">3</span>
          <div className="flow-card__body">
            <h2>Ask Memory</h2>
            <p>Ask about an object that appears below.</p>
            <form className="ask-form" onSubmit={handleAsk}>
              <label htmlFor="guardian-query">Question to test</label>
              <div className="ask-form__controls">
                <input
                  id="guardian-query"
                  name="query"
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder={suggestedQuery}
                  type="text"
                  value={query}
                />
                <button className="button button--primary" disabled={queryPending} type="submit">
                  {queryPending ? "Asking" : "Ask"}
                </button>
              </div>
            </form>
          </div>
        </article>
      </section>

      <section className="answer-panel" aria-label="Memory answer">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Answer</p>
            <h2>What Memory Guardian says</h2>
          </div>
          {queryResult ? (
            <div className="pill-row">
              <StatusPill label={sentenceCase(queryResult.confidence)} tone={queryResult.confidence === "high" ? "good" : "warn"} />
              <StatusPill label={queryResult.used_current_perception ? "Current" : "Memory"} tone={queryResult.used_current_perception ? "good" : "info"} />
            </div>
          ) : null}
        </div>
        {queryError ? <StateBlock tone="error" title="Ask failed" body={queryError} /> : null}
        {queryResult ? (
          <div className="answer">
            <p>{queryResult.answer}</p>
            <div className="answer-evidence">
              <span>Evidence</span>
              <EvidenceRefs ids={queryResult.evidence_observation_ids} label="Answer evidence" />
            </div>
            {queryResult.task_id ? <p className="muted">Recovery task opened: {queryResult.task_id}</p> : null}
          </div>
        ) : (
          <StateBlock
            title="No question asked yet"
            body={`After syncing a live object, try: "${suggestedQuery}"`}
          />
        )}
      </section>

      <section className="review-grid" aria-label="What the system currently sees">
        <CurrentObservationCard observation={currentObservation} loading={latestObservation.loading} error={latestObservation.error} />
        <MemoryCard objects={rememberedObjects} loading={objects.loading} error={objects.error} />
      </section>

      <details className="details-panel">
        <summary>Optional: tasks and alerts</summary>
        <div className="details-grid">
          <TasksMiniPanel
            tasks={tasks}
            onResolve={async (taskId, resolutionNote) => {
              const result = await resolveTask(taskId, resolutionNote);
              await refreshAll();
              return result;
            }}
            onVerify={async (taskId) => {
              const result = await verifyTask(taskId);
              await refreshAll();
              return result;
            }}
          />
          <AlertsMiniPanel
            alerts={alerts}
            onAcknowledge={async (alertId) => {
              const result = await acknowledgeAlert(alertId);
              await refreshAll();
              return result;
            }}
          />
        </div>
      </details>
    </main>
  );
}

function ConnectionTile({
  title,
  value,
  tone,
  detail
}: {
  title: string;
  value: string;
  tone: StatusTone;
  detail: string;
}) {
  return (
    <div className="connection-tile">
      <span>{title}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
      <StatusPill label={tone === "good" ? "Ready" : tone === "bad" ? "Blocked" : tone === "warn" ? "Check" : "Waiting"} tone={tone} />
    </div>
  );
}

function CurrentObservationCard({
  observation,
  loading,
  error
}: {
  observation: LatestObservationResponse["observation"] | null;
  loading: boolean;
  error?: string;
}) {
  const objects = observation?.objects ?? [];

  return (
    <section className="review-card">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Current Camera Event</p>
          <h2>Latest observation</h2>
        </div>
        <StatusPill label={`${objects.length} object${objects.length === 1 ? "" : "s"}`} tone={objects.length ? "good" : "quiet"} />
      </div>
      {loading ? (
        <StateBlock tone="loading" title="Checking observation" body="Reading the latest synced live event." />
      ) : error ? (
        <StateBlock tone="error" title="Observation unavailable" body={error} />
      ) : !observation ? (
        <StateBlock title="Nothing synced yet" body="Click Sync Live Perception after the phone node is running." />
      ) : (
        <div className="observation-simple">
          <p>{observation.scene_summary || "No scene summary available."}</p>
          <dl className="compact-meta">
            <div>
              <dt>When</dt>
              <dd>{formatDateTime(observation.timestamp_utc)}</dd>
            </div>
            <div>
              <dt>Source</dt>
              <dd>{observation.source_node_id || "Unknown node"}</dd>
            </div>
            <div>
              <dt>Model</dt>
              <dd>{observation.classification || "Unknown"}</dd>
            </div>
          </dl>
          <ObjectChips objects={objects} />
        </div>
      )}
    </section>
  );
}

function MemoryCard({
  objects,
  loading,
  error
}: {
  objects: ObjectsResponse["objects"];
  loading: boolean;
  error?: string;
}) {
  return (
    <section className="review-card">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Memory</p>
          <h2>Remembered objects</h2>
        </div>
        <StatusPill label={String(objects.length)} tone={objects.length ? "good" : "quiet"} />
      </div>
      {loading ? (
        <StateBlock tone="loading" title="Checking memory" body="Reading object memory records." />
      ) : error ? (
        <StateBlock tone="error" title="Memory unavailable" body={error} />
      ) : objects.length === 0 ? (
        <StateBlock title="No objects remembered" body="Sync a live object first." />
      ) : (
        <div className="memory-list">
          {objects.slice(0, 8).map((object) => (
            <article className="memory-item" key={object.object_key}>
              <div>
                <strong>{object.display_name}</strong>
                <span>{sentenceCase(object.status)}</span>
              </div>
              <small>
                {formatDateTime(object.last_seen_at)} · {formatPercent(object.last_confidence)}
              </small>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function ObjectChips({ objects }: { objects: NonNullable<LatestObservationResponse["observation"]>["objects"] }) {
  if (!objects?.length) {
    return <p className="muted">No object labels came through in this observation.</p>;
  }

  return (
    <div className="object-chip-list" aria-label="Objects in latest observation">
      {objects.slice(0, 10).map((object) => (
        <span className="object-chip" key={`${object.object_key}-${object.label}`}>
          {object.display_name}
          <small>{formatPercent(object.confidence)}</small>
        </span>
      ))}
    </div>
  );
}

function TasksMiniPanel({
  tasks,
  onVerify,
  onResolve
}: {
  tasks: Loadable<TasksResponse>;
  onVerify: (taskId: string) => Promise<TaskVerifyResponse>;
  onResolve: (taskId: string, resolutionNote: string) => Promise<TaskResolveResponse>;
}) {
  const openTasks = (tasks.data?.tasks ?? []).filter(
    (task) => !["verified_resolved", "dismissed"].includes(task.state)
  );

  return (
    <section className="review-card">
      <h2>Tasks</h2>
      {tasks.loading ? (
        <StateBlock tone="loading" title="Checking tasks" body="Loading open recovery tasks." />
      ) : tasks.error ? (
        <StateBlock tone="error" title="Tasks unavailable" body={tasks.error} />
      ) : openTasks.length === 0 ? (
        <StateBlock title="No open tasks" body="Recovery tasks appear when memory is used for a missing object." />
      ) : (
        <div className="mini-list">
          {openTasks.map((task) => (
            <article className="mini-row" key={task.id}>
              <div>
                <strong>{task.title}</strong>
                <p>{task.recommended_action || task.body}</p>
              </div>
              <div className="task-actions">
                <button className="button button--secondary" type="button" onClick={() => void onVerify(task.id)}>
                  Verify
                </button>
                <button
                  className="button button--secondary"
                  type="button"
                  onClick={() => void onResolve(task.id, "Resolved during local live test.")}
                >
                  Mark resolved
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function AlertsMiniPanel({
  alerts,
  onAcknowledge
}: {
  alerts: Loadable<AlertsResponse>;
  onAcknowledge: (alertId: string) => Promise<AlertAckResponse>;
}) {
  const openAlerts = (alerts.data?.alerts ?? []).filter((alert) => alert.status === "open");

  return (
    <section className="review-card">
      <h2>Alerts</h2>
      {alerts.loading ? (
        <StateBlock tone="loading" title="Checking alerts" body="Loading open safety alerts." />
      ) : alerts.error ? (
        <StateBlock tone="error" title="Alerts unavailable" body={alerts.error} />
      ) : openAlerts.length === 0 ? (
        <StateBlock title="No open alerts" body="Safety alerts appear only when live evidence creates them." />
      ) : (
        <div className="mini-list">
          {openAlerts.map((alert) => (
            <article className="mini-row" key={alert.id}>
              <div>
                <strong>{alert.title}</strong>
                <p>{alert.recommended_action || alert.body}</p>
              </div>
              <button className="button button--secondary" type="button" onClick={() => void onAcknowledge(alert.id)}>
                Acknowledge
              </button>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function backendLabel(health: Loadable<HealthResponse>): string {
  if (health.loading) {
    return "Checking";
  }
  if (health.error || !health.data?.ok) {
    return "Unavailable";
  }
  return "Connected";
}

function backendTone(health: Loadable<HealthResponse>): StatusTone {
  if (health.loading) {
    return "quiet";
  }
  if (health.error || !health.data?.ok) {
    return "bad";
  }
  return "good";
}

function afferensLabel(afferens: Loadable<AfferensStatus>): string {
  if (afferens.loading) {
    return "Checking";
  }
  if (afferens.error) {
    return "Unavailable";
  }
  if (!afferens.data) {
    return "Unknown";
  }
  return sentenceCase(afferens.data.state);
}

function afferensTone(afferens: Loadable<AfferensStatus>): StatusTone {
  if (afferens.data?.state === "live") {
    return "good";
  }
  if (afferens.data?.state === "no_live_events") {
    return "warn";
  }
  if (afferens.error || afferens.data?.state === "error" || afferens.data?.state === "invalid_key") {
    return "bad";
  }
  return "quiet";
}

function connectionLabel(health: Loadable<HealthResponse>, afferens: Loadable<AfferensStatus>): string {
  if (health.data?.ok && afferens.data?.state === "live") {
    return "Ready to test";
  }
  if (health.data?.ok) {
    return "Waiting for phone node";
  }
  return "Checking setup";
}

function connectionTone(health: Loadable<HealthResponse>, afferens: Loadable<AfferensStatus>): StatusTone {
  if (health.data?.ok && afferens.data?.state === "live") {
    return "good";
  }
  if (health.error || health.data?.ok === false) {
    return "bad";
  }
  return "warn";
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
