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
  getAfferensLatest,
  getAfferensStatus,
  getAlerts,
  getHealth,
  getLatestObservation,
  getObjects,
  getTasks,
  syncPerception
} from "@/lib/api";
import type {
  AfferensLatestResponse,
  AfferensStatus,
  AlertsResponse,
  HealthResponse,
  LatestObservationResponse,
  Loadable,
  ObjectsResponse,
  TasksResponse
} from "@/lib/types";

const POLL_MS = 10000;

export default function Home() {
  const sessionId = useMemo(() => "browser-session", []);
  const [health, setHealth] = useState<Loadable<HealthResponse>>({ loading: true });
  const [afferens, setAfferens] = useState<Loadable<AfferensStatus>>({ loading: true });
  const [latestEvent, setLatestEvent] = useState<Loadable<AfferensLatestResponse>>({ loading: true });
  const [latestObservation, setLatestObservation] = useState<Loadable<LatestObservationResponse>>({ loading: true });
  const [objects, setObjects] = useState<Loadable<ObjectsResponse>>({ loading: true });
  const [tasks, setTasks] = useState<Loadable<TasksResponse>>({ loading: true });
  const [alerts, setAlerts] = useState<Loadable<AlertsResponse>>({ loading: true });
  const [syncPending, setSyncPending] = useState(false);
  const [syncError, setSyncError] = useState<string | undefined>();

  const refreshAll = useCallback(async () => {
    await Promise.all([
      loadInto(setHealth, getHealth),
      loadInto(setAfferens, getAfferensStatus),
      loadInto(setLatestEvent, getAfferensLatest),
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

    try {
      await syncPerception();
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
            Operational shell for setup, live observation, evidence-backed memory, active tasks, and caregiver
            escalation status.
          </p>
        </div>
        <div className="header-summary" aria-label="Current Afferens event summary">
          <span>Latest event</span>
          <strong>{latestEvent.data?.status.latest_event_id || "No live event"}</strong>
          <small>{latestEvent.error || latestEvent.data?.status.message || "Waiting for backend status"}</small>
        </div>
      </section>

      <div className="dashboard-grid">
        <div className="dashboard-grid__main">
          <LiveStatusPanel health={health} afferens={afferens} onRefresh={refreshAll} />
          <ObservationPanel
            latestObservation={latestObservation}
            onSync={handleSync}
            syncError={syncError}
            syncPending={syncPending}
          />
          <ObjectMemoryTable objects={objects} />
          <ActiveTaskConsole tasks={tasks} />
        </div>

        <aside className="dashboard-grid__side" aria-label="Setup and caregiver controls">
          <NodeSetupChecklist health={health} afferens={afferens} />
          <AlertQueue alerts={alerts} />
          <AskInterface sessionId={sessionId} />
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
