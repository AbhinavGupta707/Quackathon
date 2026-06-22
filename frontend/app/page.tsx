"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  acknowledgeFamilyMessage,
  generateDiary,
  getActionEvents,
  getAfferensStatus,
  getActiveFamilyMessages,
  getDiary,
  getHealth,
  getHomeMemoryStatus,
  getHydrationSummary,
  getHomeZones,
  getObjects,
  getPerceptionModalities,
  getProvidersStatus,
  getTasks,
  getWellnessChecks,
  isUnavailableEndpoint,
  recordActionEvent,
  resolveTask,
  startHomeMemory,
  startGuidedRecovery,
  stopHomeMemory,
  verifyTask
} from "@/lib/api";
import { buildPatientHelpRequest } from "@/lib/actionTelemetry";
import { formatDateTime, objectStatusLabel, sentenceCase } from "@/lib/format";
import type {
  AfferensStatus,
  ActionEvent,
  ActionEventsResponse,
  DailyDiaryEntry,
  DiaryResponse,
  FamilyMessage,
  FamilyMessagesResponse,
  HomeZonesResponse,
  HealthResponse,
  HydrationSummaryResponse,
  LastSeenObject,
  Loadable,
  ObjectsResponse,
  PerceptionModalitiesResponse,
  ProvidersStatusResponse,
  RuntimeMonitorStatus,
  RuntimeMonitorStatusResponse,
  TasksResponse,
  WellnessChecksResponse
} from "@/lib/types";
import { AskInterface } from "@/components/AskInterface";
import { PatientMemoryRecall } from "@/components/PatientMemoryRecall";
import { ProviderReadinessPanel } from "@/components/ProviderReadinessPanel";
import { StateBlock } from "@/components/StateBlock";
import { StatusPill, type StatusTone } from "@/components/StatusPill";

const POLL_MS = 5000;
const HOME_MEMORY_POLL_SECONDS = 10;
const HOME_MEMORY_TOKEN_BUDGET_PER_HOUR = 10_000;
const SESSION_ID = "patient-home";

type PatientTab = "dashboard" | "chat";

type LocationAwareObject = LastSeenObject & {
  human_location?: string | null;
  last_seen_region_label?: string | null;
  last_seen_zone_name?: string | null;
  region_label?: string | null;
  room_name?: string | null;
  zone_name?: string | null;
};

export default function Home() {
  const todayDate = useMemo(() => toDateInputValue(new Date()), []);
  const [health, setHealth] = useState<Loadable<HealthResponse>>({ loading: true });
  const [afferens, setAfferens] = useState<Loadable<AfferensStatus>>({ loading: true });
  const [objects, setObjects] = useState<Loadable<ObjectsResponse>>({ loading: true });
  const [tasks, setTasks] = useState<Loadable<TasksResponse>>({ loading: true });
  const [zones, setZones] = useState<Loadable<HomeZonesResponse>>({ loading: true });
  const [homeMemory, setHomeMemory] = useState<Loadable<RuntimeMonitorStatusResponse>>({ loading: true });
  const [modalities, setModalities] = useState<Loadable<PerceptionModalitiesResponse>>({ loading: true });
  const [providers, setProviders] = useState<Loadable<ProvidersStatusResponse>>({ loading: true });
  const [familyMessages, setFamilyMessages] = useState<Loadable<FamilyMessagesResponse>>({ loading: true });
  const [diary, setDiary] = useState<Loadable<DiaryResponse>>({ loading: true });
  const [hydration, setHydration] = useState<Loadable<HydrationSummaryResponse>>({ loading: true });
  const [wellnessChecks, setWellnessChecks] = useState<Loadable<WellnessChecksResponse>>({ loading: true });
  const [actionEvents, setActionEvents] = useState<Loadable<ActionEventsResponse>>({ loading: true });
  const [selectedObjectKey, setSelectedObjectKey] = useState<string>("");
  const [homeActionPending, setHomeActionPending] = useState<"ambient" | "active" | "stop" | "message" | "diary" | "help" | null>(null);
  const [homeMessage, setHomeMessage] = useState<{ tone?: "error" | "success"; title: string; body: string } | null>(null);
  const [activeTab, setActiveTab] = useState<PatientTab>("dashboard");
  const [homeMemoryManualStop, setHomeMemoryManualStop] = useState(false);
  const autoHomeMemoryAttemptedRef = useRef(false);

  const rememberedObjects = useMemo(() => objects.data?.objects ?? [], [objects.data?.objects]);
  const openTasks = (tasks.data?.tasks ?? []).filter(
    (task) => !["verified_resolved", "dismissed"].includes(task.state)
  );
  const selectedObject = useMemo(
    () => rememberedObjects.find((object) => object.object_key === selectedObjectKey) ?? rememberedObjects[0] ?? null,
    [rememberedObjects, selectedObjectKey]
  );
  const visibleObjects = rememberedObjects.filter((object) => object.status === "visible_now");
  const suggestedQuery = selectedObject ? `Where is my ${selectedObject.display_name}?` : "Where are my keys?";
  const defaultZoneId = useMemo(
    () => zones.data?.zones.find((zone) => zone.is_default)?.id,
    [zones.data?.zones]
  );
  const monitor = homeMemory.data?.monitor ?? null;
  const isHomeNodeLive = Boolean(health.data?.ok && afferens.data?.state === "live");
  const homeMemoryIsOff = !monitor || ["off", "stopped", "idle", "completed"].includes(monitor.state);

  const refreshAll = useCallback(async () => {
    await Promise.all([
      loadInto(setHealth, getHealth),
      loadInto(setAfferens, getAfferensStatus),
      loadInto(setObjects, getObjects),
      loadInto(setTasks, getTasks),
      loadInto(setZones, getHomeZones),
      loadInto(setHomeMemory, getHomeMemoryStatus),
      loadInto(setModalities, getPerceptionModalities),
      loadInto(setProviders, getProvidersStatus),
      loadInto(setFamilyMessages, getActiveFamilyMessages),
      loadInto(setDiary, () => getDiary(todayDate)),
      loadInto(setHydration, () => getHydrationSummary(todayDate)),
      loadInto(setWellnessChecks, () => getWellnessChecks(todayDate)),
      loadInto(setActionEvents, () => getActionEvents({ date: todayDate, limit: 12 }))
    ]);
  }, [todayDate]);

  useEffect(() => {
    void refreshAll();
    const timer = window.setInterval(() => {
      void refreshAll();
    }, POLL_MS);

    return () => window.clearInterval(timer);
  }, [refreshAll]);

  useEffect(() => {
    if (!selectedObjectKey && rememberedObjects[0]) {
      setSelectedObjectKey(rememberedObjects[0].object_key);
    }
  }, [rememberedObjects, selectedObjectKey]);

  const handleStartHomeMemory = useCallback(async (options: { automatic?: boolean } = {}) => {
    setHomeMemoryManualStop(false);
    setHomeActionPending("ambient");
    setHomeMessage(null);
    try {
      const response = await startHomeMemory({
        max_tokens_per_hour: HOME_MEMORY_TOKEN_BUDGET_PER_HOUR,
        mode: "home_memory",
        poll_interval_seconds: HOME_MEMORY_POLL_SECONDS,
        zone_id: defaultZoneId
      });
      setHomeMemory({ data: { ok: response.ok, monitor: response.monitor, message: response.message }, loading: false });
      setHomeMessage({
        tone: "success",
        title: "Home memory is on",
        body: options.automatic
          ? "The live home node is connected, so I turned on gentle item-memory checks."
          : response.message || "I will keep checking gently in the background when the live home connection is available."
      });
      await refreshAll();
    } catch (error) {
      if (!options.automatic) {
        setHomeMessage(endpointFallbackMessage(error, "Home memory is not available yet."));
      }
    } finally {
      setHomeActionPending(null);
    }
  }, [defaultZoneId, refreshAll]);

  useEffect(() => {
    if (!isHomeNodeLive) {
      autoHomeMemoryAttemptedRef.current = false;
      return;
    }
    if (
      !homeMemoryIsOff ||
      homeMemoryManualStop ||
      homeActionPending !== null ||
      homeMemory.loading ||
      zones.loading ||
      autoHomeMemoryAttemptedRef.current
    ) {
      return;
    }

    autoHomeMemoryAttemptedRef.current = true;
    void handleStartHomeMemory({ automatic: true });
  }, [
    handleStartHomeMemory,
    homeActionPending,
    homeMemory.loading,
    homeMemoryIsOff,
    homeMemoryManualStop,
    isHomeNodeLive,
    zones.loading
  ]);

  async function handleStopHomeMemory() {
    setHomeMemoryManualStop(true);
    setHomeActionPending("stop");
    setHomeMessage(null);
    try {
      const response = await stopHomeMemory();
      setHomeMemory({ data: { ok: response.ok, monitor: response.monitor, message: response.message }, loading: false });
      setHomeMessage({
        tone: "success",
        title: "Home memory is off",
        body: response.message || "I will stop checking in the background."
      });
      await refreshAll();
    } catch (error) {
      setHomeMessage(endpointFallbackMessage(error, "Home memory controls are not available yet."));
    } finally {
      setHomeActionPending(null);
    }
  }

  async function handleFindObject(object: LastSeenObject | null) {
    if (!object) {
      setHomeMessage({
        title: "Tell me what to find",
        body: "Ask for an item first, or add live evidence from the caregiver page."
      });
      return;
    }

    setSelectedObjectKey(object.object_key);
    setHomeActionPending("active");
    setHomeMessage(null);

    try {
      const response = await startHomeMemory({
        mode: "active_recovery",
        poll_interval_seconds: 4,
        duration_seconds: 90,
        max_tokens_per_hour: 420,
        target_object_key: object.object_key,
        zone_id: defaultZoneId
      });
      setHomeMemory({ data: { ok: response.ok, monitor: response.monitor, message: response.message }, loading: false });
      setHomeMessage({
        tone: "success",
        title: `Looking for ${object.display_name}`,
        body: "Move slowly toward the likely place. I will keep checking for a short time."
      });
      await refreshAll();
    } catch (error) {
      if (isUnavailableEndpoint(error instanceof Error && "status" in error ? Number(error.status) : undefined)) {
        await startGuidedFallback(object);
      } else {
        setHomeMessage(endpointFallbackMessage(error, "I could not start the active search."));
      }
    } finally {
      setHomeActionPending(null);
    }
  }

  async function startGuidedFallback(object: LastSeenObject) {
    try {
      const response = await startGuidedRecovery(object.object_key, SESSION_ID);
      setHomeMessage({
        title: "I can guide you step by step",
        body: response.next_instruction || "Check the last place I remember, then use the caregiver page to verify."
      });
      await refreshAll();
    } catch (fallbackError) {
      setHomeMessage(endpointFallbackMessage(fallbackError, "The guided search is not available yet."));
    }
  }

  async function handleAcknowledgeFamilyMessage(message: FamilyMessage) {
    setHomeActionPending("message");
    setHomeMessage(null);
    try {
      await acknowledgeFamilyMessage(message.id);
      setHomeMessage({
        tone: "success",
        title: "Message done",
        body: "I will let the caregiver view know this family note was acknowledged."
      });
      await refreshAll();
    } catch (error) {
      setHomeMessage(endpointFallbackMessage(error, "Family message acknowledgement is not available yet."));
    } finally {
      setHomeActionPending(null);
    }
  }

  async function handleGenerateDiary() {
    setHomeActionPending("diary");
    setHomeMessage(null);
    try {
      const response = await generateDiary(todayDate);
      setDiary({ data: { date: response.diary.date, diary: response.diary }, loading: false });
      setHomeMessage({
        tone: "success",
        title: "Today was summarized",
        body: "A caregiver can review the summary when they check today's notes."
      });
    } catch (error) {
      setHomeMessage(endpointFallbackMessage(error, "Today's summary is not available yet."));
    } finally {
      setHomeActionPending(null);
    }
  }

  async function handleRequestCaregiverCheck() {
    setHomeActionPending("help");
    setHomeMessage(null);
    try {
      await recordActionEvent(buildPatientHelpRequest(afferens.data?.source_node_id || "PATIENT-HELP"));
      setHomeMessage({
        tone: "success",
        title: "Caregiver check requested",
        body: "You can stay where you are. A caregiver can review the check-in request."
      });
    } catch (error) {
      setHomeMessage(endpointFallbackMessage(error, "Caregiver check requests are not available yet."));
    } finally {
      setHomeActionPending(null);
    }
  }

  const patientGuidance = guidanceForPatient({
    afferens: afferens.data,
    health,
    monitor,
    openTaskCount: openTasks.length,
    selectedObject,
    visibleCount: visibleObjects.length
  });

  return (
    <main className="patient-shell">
      <section className="patient-hero" aria-labelledby="patient-title">
        <div className="patient-hero__copy">
          <p className="eyebrow">Afferens Memory Guardian</p>
          <h1 id="patient-title">Home Memory</h1>
          <p>{patientGuidance}</p>
        </div>
        <div className="patient-status-card" aria-label="Home memory status">
          <StatusPill label={connectionLabel(health, afferens)} tone={connectionTone(health, afferens)} />
          <strong>{homeMemoryLabel(monitor, homeMemory.loading, homeMemory.error)}</strong>
          <span>{homeMemoryStatusCopy(monitor, homeMemory.error)}</span>
          <small className="patient-sync-note">{monitorTimingCopy(monitor)}</small>
          <div className="patient-status-card__actions">
            <button className="button button--primary" disabled={homeActionPending === "ambient"} onClick={() => void handleStartHomeMemory()} type="button">
              {homeActionPending === "ambient" ? "Turning on" : "Turn on home memory"}
            </button>
            <button className="button button--secondary" disabled={homeActionPending === "stop"} onClick={() => void handleStopHomeMemory()} type="button">
              {homeActionPending === "stop" ? "Turning off" : "Turn off"}
            </button>
          </div>
          <Link className="button button--secondary" href="/caregiver">
            Caregiver view
          </Link>
        </div>
      </section>

      {homeMessage ? (
        <StateBlock
          tone={homeMessage.tone === "error" ? "error" : homeMessage.tone === "success" ? "success" : "empty"}
          title={homeMessage.title}
          body={homeMessage.body}
        />
      ) : null}

      <nav className="patient-tabs" aria-label="Patient sections">
        <button
          aria-current={activeTab === "dashboard" ? "page" : undefined}
          className="patient-tab"
          onClick={() => setActiveTab("dashboard")}
          type="button"
        >
          Dashboard
        </button>
        <button
          aria-current={activeTab === "chat" ? "page" : undefined}
          className="patient-tab"
          onClick={() => setActiveTab("chat")}
          type="button"
        >
          Chat
        </button>
      </nav>

      {activeTab === "dashboard" ? (
        <section className="patient-tab-panel" aria-label="Dashboard">
          <section className="patient-dashboard-grid">
            <DashboardItemMemory
              objects={objects}
              onSelect={(objectKey) => {
                setSelectedObjectKey(objectKey);
                setActiveTab("chat");
              }}
              selectedObjectKey={selectedObject?.object_key ?? ""}
            />
            <DashboardRecentEvents
              actionEvents={actionEvents}
              hydration={hydration}
              tasks={tasks}
              wellnessChecks={wellnessChecks}
            />
            <DashboardCaregiverNotes
              diary={diary}
              familyMessages={familyMessages}
              onAcknowledge={(message) => void handleAcknowledgeFamilyMessage(message)}
              onGenerateDiary={() => void handleGenerateDiary()}
              onRequestCheck={() => void handleRequestCaregiverCheck()}
              pending={homeActionPending}
              tasks={tasks}
              wellnessChecks={wellnessChecks}
            />
          </section>
          <details className="patient-advanced-details">
            <summary>Setup and provider status</summary>
            <div className="patient-advanced-details__body">
              <ProviderReadinessPanel
                afferens={afferens}
                homeMemory={homeMemory}
                providers={providers}
                variant="patient"
              />
              <section className="patient-secondary-grid" aria-label="Home areas and simple status">
                <PatientHomeAreasCard zones={zones} />
                <SimpleStatusCard
                  afferens={afferens}
                  health={health}
                  monitor={monitor}
                  objectCount={rememberedObjects.length}
                  openTaskCount={openTasks.length}
                  modalities={modalities}
                  providers={providers}
                />
              </section>
            </div>
          </details>
        </section>
      ) : (
        <section className="patient-tab-panel patient-chat-layout" aria-label="Chat">
          <AskInterface
            afferensState={afferens.data?.state}
            mode="patient"
            onAnswered={() => refreshAll()}
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
            sessionId={SESSION_ID}
            suggestedQuery={suggestedQuery}
            tasks={tasks.data?.tasks ?? []}
          />

          <section className="patient-guidance-card" aria-labelledby="find-item-title">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Find an item</p>
                <h2 id="find-item-title">Help me find it</h2>
              </div>
              <StatusPill label={selectedObject ? objectStatusLabel(selectedObject.status) : "Not sure yet"} tone={selectedObject?.status === "visible_now" ? "good" : "warn"} />
            </div>
            <div className="selected-object">
              <strong>{selectedObject?.display_name || "No item selected"}</strong>
              <p>{selectedObject ? lastSeenCopy(selectedObject) : "Ask about an item, or choose one I remember."}</p>
              {selectedObject ? <small>{objectTimeCopy(selectedObject)}</small> : null}
            </div>
            <button
              className="button button--primary button--large"
              disabled={homeActionPending === "active" || !selectedObject}
              onClick={() => void handleFindObject(selectedObject)}
              type="button"
            >
              {homeActionPending === "active" ? "Starting search" : "Help me find it"}
            </button>
            {rememberedObjects.length ? (
              <div className="patient-object-list" aria-label="Remembered items">
                {rememberedObjects.slice(0, 6).map((object) => (
                  <button
                    aria-pressed={object.object_key === selectedObject?.object_key}
                    className="memory-choice"
                    key={object.object_key}
                    onClick={() => setSelectedObjectKey(object.object_key)}
                    type="button"
                  >
                    <strong>{object.display_name}</strong>
                    <span>{objectStatusLabel(object.status)}</span>
                    <small>{locationPhrase(object) || objectTimeCopy(object)}</small>
                  </button>
                ))}
              </div>
            ) : (
              <StateBlock title="No remembered items yet" body="Turn on home memory, point the live view at an item, then wait for the next check." />
            )}
          </section>

          <PatientMemoryRecall />
        </section>
      )}
    </main>
  );
}

function DashboardItemMemory({
  objects,
  onSelect,
  selectedObjectKey
}: {
  objects: Loadable<ObjectsResponse>;
  onSelect: (objectKey: string) => void;
  selectedObjectKey: string;
}) {
  const rememberedObjects = objects.data?.objects ?? [];

  return (
    <section className="patient-panel dashboard-item-memory" aria-labelledby="dashboard-item-memory-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Item memory</p>
          <h2 id="dashboard-item-memory-title">Items being tracked</h2>
        </div>
        <StatusPill
          label={objects.loading ? "Checking" : `${rememberedObjects.length} item${rememberedObjects.length === 1 ? "" : "s"}`}
          tone={rememberedObjects.length ? "good" : objects.error ? "quiet" : "info"}
        />
      </div>

      {objects.loading && !objects.data ? (
        <StateBlock tone="loading" title="Checking item memory" body="Looking for live item memories from the home view." />
      ) : objects.error ? (
        <StateBlock title="Item memory is not available" body={objects.error} />
      ) : rememberedObjects.length ? (
        <div className="dashboard-item-list" aria-label="Tracked items">
          {rememberedObjects.map((object) => (
            <button
              aria-pressed={object.object_key === selectedObjectKey}
              className="dashboard-item-row"
              key={object.object_key}
              onClick={() => onSelect(object.object_key)}
              type="button"
            >
              <span>
                <strong>{object.display_name}</strong>
                <small>{locationPhrase(object) || "Location not named yet"}</small>
              </span>
              <span>
                <b>{objectStatusLabel(object.status)}</b>
                <small>{object.last_seen_at ? formatDateTime(object.last_seen_at) : "No time yet"}</small>
              </span>
            </button>
          ))}
        </div>
      ) : (
        <StateBlock
          title="No items saved right now"
          body="Turn on home memory, keep the Afferens node pointed at one item, then wait for the next live check."
        />
      )}
    </section>
  );
}

function DashboardRecentEvents({
  actionEvents,
  hydration,
  tasks,
  wellnessChecks
}: {
  actionEvents: Loadable<ActionEventsResponse>;
  hydration: Loadable<HydrationSummaryResponse>;
  tasks: Loadable<TasksResponse>;
  wellnessChecks: Loadable<WellnessChecksResponse>;
}) {
  const fallCheckActionEventIds = new Set(
    (wellnessChecks.data?.checks ?? [])
      .map((check) => {
        const actionEventId = check.metadata?.action_event_id;
        return typeof actionEventId === "string" ? actionEventId : null;
      })
      .filter((id): id is string => Boolean(id))
  );
  const actionRows = (actionEvents.data?.events ?? []).map((event) => ({
    event,
    row: {
      id: `action-${event.id}`,
      occurredAt: event.occurred_at,
      title: actionEventTitle(event),
      body: actionEventBody(event),
      label: sentenceCase(event.confidence)
    }
  }))
    .filter(({ event }) => !isFallActionEvent(event) || !fallCheckActionEventIds.has(event.id))
    .map(({ row }) => row);
  const checkRows = (wellnessChecks.data?.checks ?? [])
    .filter((check) => check.status === "open")
    .map((check) => ({
      id: `check-${check.id}`,
      occurredAt: check.occurred_at,
      title: wellnessCheckEventTitle(check),
      body: wellnessCheckEventBody(check),
      label: sentenceCase(check.severity)
    }));
  const taskRows = (tasks.data?.tasks ?? [])
    .filter((task) => !["verified_resolved", "dismissed"].includes(task.state))
    .map((task) => ({
      id: `task-${task.id}`,
      occurredAt: task.updated_at || task.created_at,
      title: task.title,
      body: task.recommended_action || task.body,
      label: sentenceCase(task.state)
    }));
  const rows = [...actionRows, ...checkRows]
    .sort((left, right) => dateScore(right.occurredAt) - dateScore(left.occurredAt))
    .slice(0, 6);
  const loading = actionEvents.loading || wellnessChecks.loading || tasks.loading || hydration.loading;
  const error = actionEvents.error || wellnessChecks.error || tasks.error || hydration.error;
  const hydrationCount = hydration.data?.summary.water_events ?? 0;

  return (
    <section className="patient-panel dashboard-recent-events" aria-labelledby="dashboard-events-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Recent events</p>
          <h2 id="dashboard-events-title">Drink, fall, and help events</h2>
        </div>
        <StatusPill label={loading ? "Checking" : rows.length ? `${rows.length} recent` : "Quiet"} tone={rows.length ? "warn" : "good"} />
      </div>

      <div className="dashboard-metric-row">
        <div>
          <span>Hydration records</span>
          <strong>{hydrationCount}</strong>
          <p>Only drink candidates or caregiver reports count. Bottle visibility alone does not.</p>
        </div>
        <div>
          <span>Fall/wellness checks</span>
          <strong>{checkRows.length}</strong>
          <p>Object-finding searches are kept separate below.</p>
        </div>
      </div>

      {taskRows.length ? (
        <details className="dashboard-task-details">
          <summary>{taskRows.length} open item search{taskRows.length === 1 ? "" : "es"}</summary>
          <div className="dashboard-event-list">
            {taskRows.map((row) => (
              <article className="dashboard-event-row dashboard-event-row--quiet" key={row.id}>
                <div>
                  <strong>{row.title}</strong>
                  <p>{row.body}</p>
                </div>
                <span>
                  <b>{row.label}</b>
                  <small>{formatDateTime(row.occurredAt)}</small>
                </span>
              </article>
            ))}
          </div>
        </details>
      ) : null}

      {rows.length ? (
        <div className="dashboard-event-list">
          {rows.map((row) => (
            <article className="dashboard-event-row" key={row.id}>
              <div>
                <strong>{row.title}</strong>
                <p>{row.body}</p>
              </div>
              <span>
                <b>{row.label}</b>
                <small>{formatDateTime(row.occurredAt)}</small>
              </span>
            </article>
          ))}
        </div>
      ) : loading ? (
        <StateBlock tone="loading" title="Checking events" body="Looking for recent drink, fall, help, or wellness records." />
      ) : error ? (
        <StateBlock title="Some event sources are not available" body={error} />
      ) : (
        <StateBlock title="No recent events" body="Drink candidates, possible fall checks, and caregiver check-ins will appear here." />
      )}
    </section>
  );
}

function DashboardCaregiverNotes({
  diary,
  familyMessages,
  onAcknowledge,
  onGenerateDiary,
  onRequestCheck,
  pending,
  tasks,
  wellnessChecks
}: {
  diary: Loadable<DiaryResponse>;
  familyMessages: Loadable<FamilyMessagesResponse>;
  onAcknowledge: (message: FamilyMessage) => void;
  onGenerateDiary: () => void;
  onRequestCheck: () => void;
  pending: "ambient" | "active" | "stop" | "message" | "diary" | "help" | null;
  tasks: Loadable<TasksResponse>;
  wellnessChecks: Loadable<WellnessChecksResponse>;
}) {
  const activeMessages = (familyMessages.data?.messages ?? []).filter((message) => message.status !== "acknowledged");
  const openChecks = (wellnessChecks.data?.checks ?? []).filter((check) => check.status === "open");
  const openTasks = (tasks.data?.tasks ?? []).filter(
    (task) => !["verified_resolved", "dismissed"].includes(task.state)
  );
  const diaryEntry = diary.data?.diary ?? null;

  return (
    <section className="patient-panel dashboard-caregiver-notes" aria-labelledby="dashboard-caregiver-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Caregiver notes</p>
          <h2 id="dashboard-caregiver-title">Family nudges and daily notes</h2>
        </div>
        <StatusPill
          label={activeMessages.length || openChecks.length || openTasks.length ? "Review" : "Quiet"}
          tone={activeMessages.length || openChecks.length || openTasks.length ? "warn" : "good"}
        />
      </div>

      <div className="dashboard-caregiver-grid">
        <div className="dashboard-note-block">
          <h3>Family nudges</h3>
          {familyMessages.loading && !familyMessages.data ? (
            <p>Checking for family notes.</p>
          ) : activeMessages.length ? (
            activeMessages.slice(0, 3).map((message) => (
              <article className="dashboard-note-row" key={message.id}>
                <div>
                  <strong>{message.title}</strong>
                  <p>{message.body}</p>
                </div>
                <button className="button button--secondary" disabled={pending === "message"} onClick={() => onAcknowledge(message)} type="button">
                  Seen
                </button>
              </article>
            ))
          ) : (
            <p>No family note is waiting.</p>
          )}
        </div>

        <div className="dashboard-note-block">
          <h3>Daily note</h3>
          {diaryEntry ? (
            <DiarySummary entry={diaryEntry} />
          ) : (
            <div className="dashboard-empty-action">
              <p>No daily note has been generated yet.</p>
              <button className="button button--secondary" disabled={pending === "diary"} onClick={onGenerateDiary} type="button">
                {pending === "diary" ? "Making note" : "Make note"}
              </button>
            </div>
          )}
        </div>

        <div className="dashboard-note-block">
          <h3>Caregiver check</h3>
          <p>{openChecks.length || openTasks.length ? "There are open checks a caregiver can review." : "No caregiver review is waiting right now."}</p>
          <button className="button button--primary" disabled={pending === "help"} onClick={onRequestCheck} type="button">
            {pending === "help" ? "Requesting" : "Ask caregiver to check"}
          </button>
        </div>
      </div>
    </section>
  );
}

function PatientHomeAreasCard({ zones }: { zones: Loadable<HomeZonesResponse> }) {
  return (
    <section className="patient-panel" aria-labelledby="areas-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Home areas</p>
          <h2 id="areas-title">Places I can use in answers</h2>
        </div>
        <StatusPill label={zones.loading ? "Checking" : `${zones.data?.zones.length ?? 0} saved`} tone={zones.data?.zones.length ? "good" : "quiet"} />
      </div>

      {zones.error ? (
        <StateBlock title="Home areas not ready" body="A caregiver can set up simple room and area names when this feature is available." />
      ) : zones.data?.zones.length ? (
        <div className="zone-chip-list">
          {zones.data.zones.map((zone) => (
            <span className="zone-chip" key={zone.id}>
              {zone.name}
              {zone.is_default ? <small>Main area</small> : null}
            </span>
          ))}
        </div>
      ) : zones.loading ? (
        <StateBlock tone="loading" title="Checking home areas" body="Looking for named rooms and areas." />
      ) : (
        <StateBlock title="No areas named yet" body="A caregiver can name simple areas like Study desk or Kitchen counter." />
      )}

      <Link className="button button--secondary" href="/caregiver">
        Set up areas
      </Link>
    </section>
  );
}

function DiarySummary({ entry }: { entry: DailyDiaryEntry }) {
  return (
    <div className="diary-summary">
      <p>{entry.summary}</p>
      {entry.highlights.length ? (
        <ul className="patient-note-list" aria-label="Today highlights">
          {entry.highlights.slice(0, 3).map((highlight) => (
            <li key={highlight}>{highlight}</li>
          ))}
        </ul>
      ) : null}
      {entry.needs_review.length ? (
        <p className="muted">A caregiver may want to check: {entry.needs_review.slice(0, 2).join("; ")}</p>
      ) : null}
    </div>
  );
}

function SimpleStatusCard({
  afferens,
  health,
  modalities,
  monitor,
  objectCount,
  openTaskCount,
  providers
}: {
  afferens: Loadable<AfferensStatus>;
  health: Loadable<HealthResponse>;
  modalities: Loadable<PerceptionModalitiesResponse>;
  monitor: RuntimeMonitorStatus | null;
  objectCount: number;
  openTaskCount: number;
  providers: Loadable<ProvidersStatusResponse>;
}) {
  const readiness = summarizeReadiness(modalities, providers);

  return (
    <section className="patient-panel" aria-labelledby="simple-status-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Today</p>
          <h2 id="simple-status-title">Simple check</h2>
        </div>
        <StatusPill label={connectionLabel(health, afferens)} tone={connectionTone(health, afferens)} />
      </div>
      <div className="patient-status-list">
        <div>
          <span>Home connection</span>
          <strong>{afferens.data?.state === "live" ? "Connected" : "Needs setup"}</strong>
          <p>{afferens.data?.message || afferens.error || "Checking the home connection."}</p>
        </div>
        <div>
          <span>Remembered items</span>
          <strong>{objectCount}</strong>
          <p>{objectCount ? "I have recent item memories." : "No item memories yet."}</p>
        </div>
        <div>
          <span>Open help</span>
          <strong>{openTaskCount}</strong>
          <p>{openTaskCount ? "Some searches or checks are still open." : "No open searches right now."}</p>
        </div>
        <div>
          <span>Last check</span>
          <strong>{formatDateTime(monitor?.last_tick_at)}</strong>
          <p>{monitor?.last_error ? `Last issue: ${monitor.last_error}` : "No recent issue reported."}</p>
        </div>
        <div>
          <span>Live senses</span>
          <strong>{readiness.modalitiesLabel}</strong>
          <p>{readiness.modalitiesCopy}</p>
        </div>
        <div>
          <span>Providers</span>
          <strong>{readiness.providersLabel}</strong>
          <p>{readiness.providersCopy}</p>
        </div>
      </div>
    </section>
  );
}

function connectionLabel(health: Loadable<HealthResponse>, afferens: Loadable<AfferensStatus>): string {
  if (health.data?.ok && afferens.data?.state === "live") {
    return "Home connected";
  }
  if (health.data?.ok) {
    return "Waiting for home view";
  }
  return "Checking";
}

function connectionTone(health: Loadable<HealthResponse>, afferens: Loadable<AfferensStatus>): StatusTone {
  if (health.data?.ok && afferens.data?.state === "live") {
    return "good";
  }
  if (health.error || health.data?.ok === false || afferens.data?.state === "invalid_key") {
    return "bad";
  }
  return "warn";
}

function homeMemoryLabel(monitor: RuntimeMonitorStatus | null, loading: boolean, error?: string): string {
  if (loading) {
    return "Checking home memory";
  }
  if (error) {
    return "Home memory unavailable";
  }
  if (!monitor || ["off", "stopped", "idle"].includes(monitor.state)) {
    return "Home memory is off";
  }
  if (monitor.mode === "active_recovery") {
    return "Looking for your item";
  }
  return "Home memory is on";
}

function homeMemoryStatusCopy(monitor: RuntimeMonitorStatus | null, error?: string): string {
  if (error) {
    return "This feature may still be starting on the backend. Caregiver controls are still available.";
  }
  if (!monitor) {
    return "Turn it on when the live home view is ready.";
  }
  if (monitor.target_object_key) {
    return `Searching for ${monitor.target_object_key.replace(/_/g, " ")}.`;
  }
  if (monitor.last_error) {
    return `Needs checking: ${monitor.last_error}`;
  }
  return monitor.mode === "home_memory" ? "I will keep gentle watch for item memories." : sentenceCase(monitor.state);
}

function monitorTimingCopy(monitor: RuntimeMonitorStatus | null): string {
  if (!monitor || ["off", "stopped", "idle"].includes(monitor.state)) {
    return "Dashboard refreshes every 10 seconds. Turn on home memory to pull live Afferens events.";
  }
  return `Dashboard refreshes every 10 seconds. Home memory checks Afferens about every ${monitor.poll_interval_seconds} seconds.`;
}

function summarizeReadiness(
  modalities: Loadable<PerceptionModalitiesResponse>,
  providers: Loadable<ProvidersStatusResponse>
): {
  modalitiesCopy: string;
  modalitiesLabel: string;
  providersCopy: string;
  providersLabel: string;
} {
  const modalityList = modalities.data?.modalities ?? [];
  const vision = modalityList.find((item) => item.modality.toUpperCase() === "VISION");
  const liveNonVisionCount = modalityList.filter(
    (item) => item.modality.toUpperCase() !== "VISION" && item.state === "available"
  ).length;

  let modalitiesLabel = "Checking";
  let modalitiesCopy = "Looking for live Afferens modality readiness.";

  if (modalities.error) {
    modalitiesLabel = "Vision only";
    modalitiesCopy = "Modality probing is not ready yet, so only Vision should be assumed.";
  } else if (vision) {
    modalitiesLabel = vision.state === "available" ? "Vision live" : "Vision waiting";
    modalitiesCopy =
      liveNonVisionCount > 0
        ? `${liveNonVisionCount} additional modality ${liveNonVisionCount === 1 ? "is" : "are"} reported live.`
        : "No non-vision modality is being treated as live unless the backend reports it.";
  } else if (!modalities.loading) {
    modalitiesLabel = "Not reported";
    modalitiesCopy = "The backend has not reported live modality readiness yet.";
  }

  const providerList = providers.data?.providers ?? [];
  const afferens = providerList.find((item) => item.provider === "afferens");
  const fireworks = providerList.find((item) => item.provider === "fireworks");
  const semanticMemory = providerList.find((item) => item.provider === "semantic_memory");

  let providersLabel = "Checking";
  let providersCopy = "Looking for home memory and answer readiness.";

  if (providers.error) {
    providersLabel = "Not reported";
    providersCopy = "Answer readiness is unavailable. A caregiver can check setup.";
  } else if (afferens || fireworks || semanticMemory) {
    providersLabel = fireworks?.state === "configured" || fireworks?.state === "live" ? "Enhanced help" : "Local help";
    providersCopy =
      semanticMemory?.state === "lexical" || semanticMemory?.state === "deterministic_lexical"
        ? "I can use local remembered notes; broader vector memory is not reported live."
        : fireworks
          ? "A model helper may improve wording after evidence is found."
          : "Answer helper readiness has not been reported yet.";
  } else if (!providers.loading) {
    providersLabel = "Not reported";
    providersCopy = "Answer helper readiness has not been reported by the backend yet.";
  }

  return {
    modalitiesCopy,
    modalitiesLabel,
    providersCopy,
    providersLabel
  };
}

function locationPhrase(object: LastSeenObject): string {
  const extended = object as LocationAwareObject;
  const region = extended.human_location || extended.last_seen_region_label || extended.region_label || object.last_seen_relative_location;
  const room = extended.last_seen_zone_name || extended.zone_name || extended.room_name || object.last_seen_room;

  if (region && room && !region.toLowerCase().includes(room.toLowerCase())) {
    return `${region} in ${room}`;
  }
  return region || room || "";
}

function objectTimeCopy(object: LastSeenObject): string {
  if (!object.last_seen_at) {
    return "No time recorded yet.";
  }
  return object.status === "visible_now"
    ? `Current home view, ${formatDateTime(object.last_seen_at)}.`
    : `Last seen ${formatDateTime(object.last_seen_at)}.`;
}

function actionEventTitle(event: ActionEvent): string {
  if (isFallActionEvent(event)) {
    return "Possible fall candidate";
  }
  if (event.type === "drink_candidate") {
    return "Possible drink logged";
  }
  if (event.source === "patient_help_request") {
    return "Caregiver check requested";
  }
  return sentenceCase(event.type);
}

function wellnessCheckEventTitle(check: WellnessChecksResponse["checks"][number]): string {
  if (check.type === "possible_fall_check") {
    return "Possible fall candidate";
  }
  return check.title;
}

function wellnessCheckEventBody(check: WellnessChecksResponse["checks"][number]): string {
  if (check.type === "possible_fall_check") {
    return "This notification has been escalated to the caregiver for a possible fall.";
  }
  return check.body;
}

function actionEventBody(event: ActionEvent): string {
  const place = event.zone_name ? ` near ${event.zone_name}` : "";
  if (isFallActionEvent(event)) {
    return "This notification has been escalated to the caregiver for a possible fall.";
  }
  if (event.type === "drink_candidate") {
    return `A drink-action candidate was recorded${place}. Seeing a bottle alone does not count.`;
  }
  if (event.source === "patient_help_request") {
    return "The patient asked for a caregiver check-in.";
  }
  return `Recorded from ${sentenceCase(event.source)}${place}.`;
}

function isFallActionEvent(event: ActionEvent): boolean {
  return event.type === "fall_candidate" || event.type === "fall_escalated";
}

function dateScore(value?: string | null): number {
  if (!value) {
    return 0;
  }
  const score = new Date(value).getTime();
  return Number.isFinite(score) ? score : 0;
}

function lastSeenCopy(object: LastSeenObject): string {
  const place = locationPhrase(object);
  if (object.status === "visible_now") {
    return place ? `I can see it now near ${place}.` : "I can see it now in the current home view.";
  }
  if (place) {
    return `I last remember it near ${place}.`;
  }
  return "I have seen it before, but I am not sure where yet.";
}

function guidanceForPatient({
  afferens,
  health,
  monitor,
  openTaskCount,
  selectedObject,
  visibleCount
}: {
  afferens?: AfferensStatus;
  health: Loadable<HealthResponse>;
  monitor: RuntimeMonitorStatus | null;
  openTaskCount: number;
  selectedObject: LastSeenObject | null;
  visibleCount: number;
}): string {
  if (health.error) {
    return "I need the home helper service before I can answer.";
  }
  if (afferens?.state && afferens.state !== "live") {
    return "I can use remembered places, but the live home view is not connected yet.";
  }
  if (monitor?.mode === "active_recovery" && monitor.target_object_key) {
    return `I am looking for ${monitor.target_object_key.replace(/_/g, " ")}. Move slowly and I will keep checking.`;
  }
  if (selectedObject?.status === "visible_now") {
    return `${selectedObject.display_name} is visible now.`;
  }
  if (openTaskCount) {
    return "There is an open search. I can help you continue it.";
  }
  if (visibleCount) {
    return "I can see some items now. Ask me where something is.";
  }
  return "Ask me where an item is, or choose something I remember.";
}

function endpointFallbackMessage(error: unknown, fallback: string): { tone?: "error" | "success"; title: string; body: string } {
  const status = error instanceof Error && "status" in error ? Number(error.status) : undefined;
  if (isUnavailableEndpoint(status)) {
    return {
      title: "Feature not ready yet",
      body: fallback
    };
  }

  return {
    tone: "error",
    title: "Something went wrong",
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
