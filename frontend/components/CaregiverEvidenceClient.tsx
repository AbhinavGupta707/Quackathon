"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  acknowledgeAlert,
  getAfferensStatus,
  getAmbientStatus,
  getAlerts,
  getHealth,
  getLatestObservation,
  getObjects,
  getProvidersStatus,
  getTasks,
  resolveTask,
  syncPerception,
  verifyTask
} from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type {
  AfferensStatus,
  AmbientStatusResponse,
  AlertsResponse,
  HealthResponse,
  LatestObservationResponse,
  Loadable,
  ObjectsResponse,
  ProvidersStatusResponse,
  SyncResponse,
  TasksResponse
} from "@/lib/types";
import { ActiveTaskConsole } from "./ActiveTaskConsole";
import { ActuationReadinessPanel } from "./ActuationReadinessPanel";
import { AlertQueue } from "./AlertQueue";
import { AskInterface } from "./AskInterface";
import { CaregiverActionReviewClient } from "./CaregiverActionReviewClient";
import { CaregiverDailyCareClient } from "./CaregiverDailyCareClient";
import { CaregiverSemanticMemoryReview } from "./CaregiverSemanticMemoryReview";
import { CaregiverWellnessClient } from "./CaregiverWellnessClient";
import { LiveStatusPanel } from "./LiveStatusPanel";
import { ObjectMemoryTable } from "./ObjectMemoryTable";
import { ObservationPanel } from "./ObservationPanel";
import { ProviderReadinessPanel } from "./ProviderReadinessPanel";
import { StateBlock } from "./StateBlock";
import { StatusPill, type StatusTone } from "./StatusPill";

const POLL_MS = 10000;

export function CaregiverEvidenceClient() {
  const sessionId = useMemo(() => "caregiver-review", []);
  const [health, setHealth] = useState<Loadable<HealthResponse>>({ loading: true });
  const [afferens, setAfferens] = useState<Loadable<AfferensStatus>>({ loading: true });
  const [latestObservation, setLatestObservation] = useState<Loadable<LatestObservationResponse>>({ loading: true });
  const [objects, setObjects] = useState<Loadable<ObjectsResponse>>({ loading: true });
  const [tasks, setTasks] = useState<Loadable<TasksResponse>>({ loading: true });
  const [alerts, setAlerts] = useState<Loadable<AlertsResponse>>({ loading: true });
  const [ambient, setAmbient] = useState<Loadable<AmbientStatusResponse>>({ loading: true });
  const [providers, setProviders] = useState<Loadable<ProvidersStatusResponse>>({ loading: true });
  const [syncPending, setSyncPending] = useState(false);
  const [syncError, setSyncError] = useState<string | undefined>();
  const [syncResult, setSyncResult] = useState<SyncResponse | null>(null);

  const refreshAll = useCallback(async () => {
    await Promise.all([
      loadInto(setHealth, getHealth),
      loadInto(setAfferens, getAfferensStatus),
      loadInto(setLatestObservation, getLatestObservation),
      loadInto(setObjects, getObjects),
      loadInto(setTasks, getTasks),
      loadInto(setAlerts, getAlerts),
      loadInto(setAmbient, getAmbientStatus),
      loadInto(setProviders, getProvidersStatus)
    ]);
  }, []);

  useEffect(() => {
    void refreshAll();
    const timer = window.setInterval(() => {
      void refreshAll();
    }, POLL_MS);

    return () => window.clearInterval(timer);
  }, [refreshAll]);

  async function handleSync(): Promise<SyncResponse | null> {
    setSyncPending(true);
    setSyncError(undefined);
    setSyncResult(null);

    try {
      const result = await syncPerception();
      setSyncResult(result);
      await refreshAll();
      return result;
    } catch (error) {
      setSyncError(error instanceof Error ? error.message : "Live perception sync failed.");
      throw error;
    } finally {
      setSyncPending(false);
    }
  }

  const observation = latestObservation.data?.observation ?? null;
  const activeTasks = (tasks.data?.tasks ?? []).filter(
    (task) => !["verified_resolved", "dismissed"].includes(task.state)
  );
  const openAlerts = (alerts.data?.alerts ?? []).filter((alert) => alert.status === "open");

  return (
    <main className="caregiver-shell">
      <section className="caregiver-topbar" aria-labelledby="caregiver-title">
        <div>
          <p className="eyebrow">Caregiver Test Console</p>
          <h1 id="caregiver-title">Drink and fall testing</h1>
          <p>Start the webcam Action Node, perform one action, then check the event list.</p>
        </div>
        <nav className="topbar-actions" aria-label="Console navigation">
          <Link className="button button--secondary" href="/">
            Test console
          </Link>
          <button className="button button--secondary" onClick={() => void refreshAll()} type="button">
            Refresh
          </button>
        </nav>
      </section>

      <section className="connection-strip" aria-label="Caregiver review status">
        <ReviewMetric title="Backend" value={health.data?.ok ? "Connected" : health.loading ? "Checking" : "Unavailable"} tone={health.data?.ok ? "good" : health.error ? "bad" : "warn"} detail={health.error || "Health endpoint"} />
        <ReviewMetric title="Live Node" value={afferens.data?.state ? sentence(afferens.data.state) : afferens.loading ? "Checking" : "Unavailable"} tone={toneForAfferens(afferens)} detail={afferens.data?.source_node_id || afferens.error || "No node yet"} />
        <ReviewMetric title="Evidence" value={observation?.id ? "Latest synced" : "None"} tone={observation?.id ? "good" : "quiet"} detail={observation?.id || "Run sync"} />
        <ReviewMetric title="Queue" value={`${activeTasks.length} tasks / ${openAlerts.length} alerts`} tone={activeTasks.length || openAlerts.length ? "warn" : "quiet"} detail="Actionable items" />
      </section>

      <CaregiverActionReviewClient />

      {health.error ? (
        <StateBlock
          tone="error"
          title="Backend unavailable"
          body="Start the backend before diagnosing Afferens, task, alert, or actuation behavior."
        />
      ) : afferens.data?.state === "no_live_events" ? (
        <StateBlock
          title="No live node"
          body="Open the official Afferens node setup, then sync once live Vision events are available."
        />
      ) : null}

      <details className="caregiver-diagnostics">
        <summary>Show hydration review, object memory, diary, and advanced caregiver tools</summary>
        <CaregiverWellnessClient />
        <CaregiverDailyCareClient />
        <section className="caregiver-grid" aria-label="Evidence and action review">
          <div className="caregiver-grid__main">
            <ObservationPanel
              latestObservation={latestObservation}
              onSync={() => void handleSync()}
              syncError={syncError}
              syncPending={syncPending}
              syncResult={syncResult}
            />
            <ObjectMemoryTable objects={objects} />
            <ActiveTaskConsole
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
          </div>

          <div className="caregiver-grid__side">
            <LiveStatusPanel health={health} afferens={afferens} onRefresh={() => void refreshAll()} />
            <ProviderReadinessPanel
              afferens={afferens}
              providers={providers}
              variant="caregiver"
            />
            <AmbientDebugPanel ambient={ambient} />
            <CaregiverSemanticMemoryReview />
            <AskInterface
              afferensState={afferens.data?.state}
              onAnswered={() => refreshAll()}
              onResolve={async (taskId, resolutionNote) => {
                const result = await resolveTask(taskId, resolutionNote);
                await refreshAll();
                return result;
              }}
              onSync={handleSync}
              onVerify={async (taskId) => {
                const result = await verifyTask(taskId);
                await refreshAll();
                return result;
              }}
              sessionId={sessionId}
              tasks={tasks.data?.tasks ?? []}
            />
            <AlertQueue
              alerts={alerts}
              onAcknowledge={async (alertId) => {
                const result = await acknowledgeAlert(alertId);
                await refreshAll();
                return result;
              }}
            />
            <ActuationReadinessPanel afferens={afferens} alerts={alerts} tasks={tasks} />
          </div>
        </section>
      </details>
    </main>
  );
}

function AmbientDebugPanel({ ambient }: { ambient: Loadable<AmbientStatusResponse> }) {
  const monitor = ambient.data?.monitor ?? null;

  return (
    <section className="review-card">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Ambient Monitor</p>
          <h2>Cadence and token review</h2>
        </div>
        <StatusPill
          label={ambient.loading ? "Checking" : monitor?.state ? sentence(monitor.state) : "Unavailable"}
          tone={monitor ? "info" : ambient.error ? "quiet" : "warn"}
        />
      </div>
      {ambient.loading ? (
        <StateBlock tone="loading" title="Checking monitor" body="Loading ambient monitor status." />
      ) : ambient.error ? (
        <StateBlock
          title="Ambient endpoints unavailable"
          body="Patient mode will show an unavailable state until home-region backend endpoints are available."
        />
      ) : monitor ? (
        <dl className="compact-meta compact-meta--two">
          <div>
            <dt>Mode</dt>
            <dd>{sentence(monitor.mode)}</dd>
          </div>
          <div>
            <dt>Cadence</dt>
            <dd>{monitor.poll_interval_seconds}s</dd>
          </div>
          <div>
            <dt>Tokens per call</dt>
            <dd>{monitor.estimated_afferens_tokens_per_call ?? "Unknown"}</dd>
          </div>
          <div>
            <dt>Target</dt>
            <dd>{monitor.target_object_key || "None"}</dd>
          </div>
          <div>
            <dt>Last sync</dt>
            <dd>{formatDateTime(monitor.last_sync_at)}</dd>
          </div>
          <div>
            <dt>Last error</dt>
            <dd>{monitor.last_error || "None"}</dd>
          </div>
        </dl>
      ) : (
        <StateBlock title="No monitor status" body="The backend returned no ambient monitor state." />
      )}
    </section>
  );
}

function ReviewMetric({
  title,
  value,
  detail,
  tone
}: {
  title: string;
  value: string;
  detail: string;
  tone: StatusTone;
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

function toneForAfferens(afferens: Loadable<AfferensStatus>): StatusTone {
  if (afferens.data?.state === "live") {
    return "good";
  }
  if (afferens.error || ["missing_key", "invalid_key", "inactive_key", "error"].includes(afferens.data?.state ?? "")) {
    return "bad";
  }
  if (afferens.loading || afferens.data?.state === "no_live_events") {
    return "warn";
  }
  return "quiet";
}

function sentence(value?: string | null): string {
  if (!value) {
    return "Unknown";
  }
  return value.replace(/_/g, " ").replace(/\b\w/g, (match) => match.toUpperCase());
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
