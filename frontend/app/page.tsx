"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ActiveTaskConsole } from "@/components/ActiveTaskConsole";
import { AlertQueue } from "@/components/AlertQueue";
import { AskInterface } from "@/components/AskInterface";
import { LiveStatusPanel } from "@/components/LiveStatusPanel";
import { NodeSetupChecklist } from "@/components/NodeSetupChecklist";
import { ObjectMemoryTable } from "@/components/ObjectMemoryTable";
import { ObservationPanel } from "@/components/ObservationPanel";
import {
  acknowledgeAlert,
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
import type {
  AfferensStatus,
  AlertsResponse,
  HealthResponse,
  LatestObservationResponse,
  Loadable,
  ObjectsResponse,
  SyncResponse,
  TasksResponse
} from "@/lib/types";

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

  return (
    <main>
      <section className="app-header" aria-labelledby="app-title">
        <div>
          <p className="eyebrow">Afferens Memory Guardian</p>
          <h1 id="app-title">Live Home Assistance Console</h1>
          <p>
            Evidence-backed memory, object recovery questions, active verification tasks, and conservative caregiver
            placeholders from live Afferens perception.
          </p>
        </div>
        <div className="header-summary" aria-label="Current Afferens event summary">
          <span>Latest event</span>
          <strong>{afferens.data?.latest_event_id || "No live event"}</strong>
          <small>{afferens.error || afferens.data?.message || "Waiting for backend status"}</small>
        </div>
      </section>

      <section className="status-strip" aria-label="Live memory console summary">
        <div>
          <span>Afferens state</span>
          <strong>{afferens.data ? afferens.data.state.replace(/_/g, " ") : afferens.loading ? "checking" : "unavailable"}</strong>
        </div>
        <div>
          <span>Remembered objects</span>
          <strong>{objects.data?.objects.length ?? (objects.loading ? "..." : "0")}</strong>
        </div>
        <div>
          <span>Open tasks</span>
          <strong>
            {tasks.data?.tasks.filter((task) => !["verified_resolved", "dismissed"].includes(task.state)).length ??
              (tasks.loading ? "..." : "0")}
          </strong>
        </div>
        <div>
          <span>Latest observation</span>
          <strong>{latestObservation.data?.observation?.id || "not available"}</strong>
        </div>
      </section>

      <div className="dashboard-grid">
        <div className="dashboard-grid__main">
          <LiveStatusPanel health={health} afferens={afferens} onRefresh={() => void refreshAll()} />
          <ObservationPanel
            latestObservation={latestObservation}
            onSync={handleSync}
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

        <aside className="dashboard-grid__side" aria-label="Setup and caregiver controls">
          <NodeSetupChecklist health={health} afferens={afferens} />
          <AlertQueue
            alerts={alerts}
            onAcknowledge={async (alertId) => {
              const result = await acknowledgeAlert(alertId);
              await refreshAll();
              return result;
            }}
          />
          <AskInterface sessionId={sessionId} onAnswered={() => void refreshAll()} />
        </aside>
      </div>
    </main>
  );
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
