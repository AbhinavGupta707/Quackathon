"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { CaregiverEvidenceClient } from "@/components/CaregiverEvidenceClient";
import { StateBlock } from "@/components/StateBlock";
import { StatusPill, type StatusTone } from "@/components/StatusPill";
import {
  acknowledgeAlert,
  acknowledgeFamilyMessage,
  acknowledgeWellnessCheck,
  captureFrameForTask,
  createHomeZone,
  getActionEvents,
  getActionRuntimeStatus,
  getAfferensStatus,
  getAlerts,
  getFamilyMessages,
  getHomeZones,
  getHydrationSummary,
  getTasks,
  getWellnessChecks,
  triggerAssistiveAlarm,
  verifyTask
} from "@/lib/api";
import { formatDateTime, sentenceCase } from "@/lib/format";
import type {
  ActionEvent,
  ActionEventsResponse,
  ActionRuntimeStatusResponse,
  ActuationResponse,
  AfferensStatus,
  Alert,
  AlertsResponse,
  FamilyMessage,
  FamilyMessagesResponse,
  HomeZoneRoomType,
  HomeZonesResponse,
  HydrationSummaryResponse,
  Loadable,
  Task,
  TasksResponse,
  WellnessCheck,
  WellnessChecksResponse
} from "@/lib/types";

type RegionFormState = {
  aliases: string;
  is_default: boolean;
  name: string;
  room_type: HomeZoneRoomType;
};

const SUGGESTED_REGIONS: RegionFormState[] = [
  { name: "Study desk", room_type: "study", aliases: "desk, computer table, paperwork area", is_default: true },
  { name: "Kitchen counter", room_type: "kitchen", aliases: "counter, kettle area, sink side", is_default: false },
  { name: "Living room table", room_type: "living_room", aliases: "coffee table, sofa table, front room", is_default: false },
  { name: "Bedroom bedside", room_type: "bedroom", aliases: "bedside table, nightstand", is_default: false }
];

const EMPTY_REGION_FORM = SUGGESTED_REGIONS[0];
const NOTIFICATION_POLL_MS = 15000;

export default function CaregiverPage() {
  return (
    <>
      {process.env.CAREGIVER_ACCESS_ENABLED === "true" ? (
        <form className="access-signout" method="post" action="/api/caregiver-access">
          <input type="hidden" name="intent" value="logout" />
          <button className="button button--secondary" type="submit">
            Leave caregiver review
          </button>
        </form>
      ) : null}
      <CaregiverEvidenceClient />
      <RegionCalibrationSetup />
      <CaregiverNotificationCenter />
    </>
  );
}

function RegionCalibrationSetup() {
  const [zones, setZones] = useState<Loadable<HomeZonesResponse>>({ loading: true });
  const [form, setForm] = useState<RegionFormState>(EMPTY_REGION_FORM);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<{ tone?: "error" | "success"; title: string; body: string } | null>(null);

  const refreshZones = useCallback(async () => {
    setZones((previous) => ({ ...previous, loading: true, error: undefined }));
    try {
      const data = await getHomeZones();
      setZones({ data, loading: false });
    } catch (error) {
      setZones({
        loading: false,
        error: error instanceof Error ? error.message : "Home area setup is unavailable."
      });
    }
  }, []);

  useEffect(() => {
    void refreshZones();
  }, [refreshZones]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = form.name.trim();

    if (!name) {
      setMessage({
        title: "Name the area",
        body: "Use a simple label the patient or caregiver would actually say, such as Study desk."
      });
      return;
    }

    setPending(true);
    setMessage(null);
    try {
      const response = await createHomeZone({
        name,
        room_type: form.room_type,
        aliases: form.aliases
          .split(",")
          .map((alias) => alias.trim())
          .filter(Boolean),
        is_default: form.is_default
      });
      setMessage({
        tone: "success",
        title: "Area saved",
        body: `${response.zone.name} can be used for human-readable object locations.`
      });
      await refreshZones();
    } catch (error) {
      setMessage({
        tone: "error",
        title: "Area not saved",
        body: error instanceof Error ? error.message : "Home area setup is unavailable."
      });
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="caregiver-region-setup" aria-labelledby="caregiver-region-title">
      <div className="caregiver-region-setup__header">
        <div>
          <p className="eyebrow">Region Setup</p>
          <h1 id="caregiver-region-title">Home memory areas</h1>
          <p>Use simple rooms and areas so answers read like &quot;last seen near the desk area&quot; instead of raw evidence references.</p>
        </div>
        <div className="region-setup-summary" aria-label="Saved home area count">
          <span>Saved areas</span>
          <strong>{zones.data?.zones.length ?? 0}</strong>
          <small>{zones.loading ? "Checking" : zones.error ? "Setup unavailable" : "Simple labels only"}</small>
        </div>
      </div>

      <div className="region-setup-grid">
        <div className="region-setup-panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Saved Labels</p>
              <h2>Rooms and nearby areas</h2>
            </div>
          </div>
          {zones.error ? (
            <div className="region-empty-state">
              <strong>Region endpoint unavailable</strong>
              <p>{zones.error}</p>
            </div>
          ) : zones.data?.zones.length ? (
            <div className="region-list">
              {zones.data.zones.map((zone) => (
                <article className="region-row" key={zone.id}>
                  <div>
                    <strong>{zone.name}</strong>
                    <p>{sentenceCase(zone.room_type)}{zone.aliases.length ? `, also: ${zone.aliases.slice(0, 3).join(", ")}` : ""}</p>
                  </div>
                  {zone.is_default ? <span>Main area</span> : null}
                </article>
              ))}
            </div>
          ) : zones.loading ? (
            <div className="region-empty-state">
              <strong>Checking areas</strong>
              <p>Loading saved room and area labels.</p>
            </div>
          ) : (
            <div className="region-empty-state">
              <strong>No areas saved yet</strong>
              <p>Start with one camera view, one room, and two or three patient-friendly area names.</p>
            </div>
          )}
        </div>

        <form className="region-setup-panel region-form" onSubmit={handleSubmit}>
          <div className="section-heading">
            <div>
              <p className="eyebrow">Calibrate</p>
              <h2>Add a simple area</h2>
            </div>
          </div>

          <div className="suggested-zone-list" aria-label="Suggested region labels">
            {SUGGESTED_REGIONS.map((suggestion) => (
              <button className="zone-suggestion" key={suggestion.name} onClick={() => setForm(suggestion)} type="button">
                {suggestion.name}
              </button>
            ))}
          </div>

          <div className="zone-form">
            <label>
              Area name
              <input
                onChange={(event) => setForm({ ...form, name: event.target.value })}
                placeholder="Study desk"
                type="text"
                value={form.name}
              />
            </label>
            <label>
              Kind of room
              <select
                onChange={(event) => setForm({ ...form, room_type: event.target.value as HomeZoneRoomType })}
                value={form.room_type}
              >
                <option value="study">Study</option>
                <option value="kitchen">Kitchen</option>
                <option value="bedroom">Bedroom</option>
                <option value="living_room">Living room</option>
                <option value="hallway">Hallway</option>
                <option value="bathroom">Bathroom</option>
                <option value="other">Other</option>
              </select>
            </label>
            <label className="zone-form__wide">
              Other names
              <input
                onChange={(event) => setForm({ ...form, aliases: event.target.value })}
                placeholder="desk, computer table"
                type="text"
                value={form.aliases}
              />
            </label>
            <label className="checkbox-row">
              <input
                checked={form.is_default}
                onChange={(event) => setForm({ ...form, is_default: event.target.checked })}
                type="checkbox"
              />
              Use for the main camera view
            </label>
          </div>

          {message ? (
            <div className={`region-message${message.tone === "error" ? " region-message--error" : message.tone === "success" ? " region-message--success" : ""}`}>
              <strong>{message.title}</strong>
              <p>{message.body}</p>
            </div>
          ) : null}

          <button className="button button--primary" disabled={pending} type="submit">
            {pending ? "Saving area" : "Save area"}
          </button>
        </form>
      </div>
    </section>
  );
}

type BrowserNotificationState = NotificationPermission | "unsupported" | "checking";

type QueueItemKind =
  | "possible_fall"
  | "hydration_prompt"
  | "family_prompt"
  | "recovery_task"
  | "actuation_verification";

type CaregiverQueueItem = {
  actionEventId?: string;
  alertId?: string;
  body: string;
  evidenceIds: string[];
  familyMessageId?: string;
  id: string;
  kind: QueueItemKind;
  occurredAt?: string | null;
  severity: "low" | "medium" | "high";
  taskId?: string;
  title: string;
  wellnessCheckId?: string;
};

type NotificationActionState = {
  body?: string;
  loading?: "ack" | "verify" | "alarm" | "capture" | "notify";
  title?: string;
  tone?: "error" | "success";
};

function CaregiverNotificationCenter() {
  const todayDate = useMemo(() => toDateInputValue(new Date()), []);
  const [afferens, setAfferens] = useState<Loadable<AfferensStatus>>({ loading: true });
  const [runtime, setRuntime] = useState<Loadable<ActionRuntimeStatusResponse>>({ loading: true });
  const [actionEvents, setActionEvents] = useState<Loadable<ActionEventsResponse>>({ loading: true });
  const [wellnessChecks, setWellnessChecks] = useState<Loadable<WellnessChecksResponse>>({ loading: true });
  const [hydration, setHydration] = useState<Loadable<HydrationSummaryResponse>>({ loading: true });
  const [familyMessages, setFamilyMessages] = useState<Loadable<FamilyMessagesResponse>>({ loading: true });
  const [tasks, setTasks] = useState<Loadable<TasksResponse>>({ loading: true });
  const [alerts, setAlerts] = useState<Loadable<AlertsResponse>>({ loading: true });
  const [browserPermission, setBrowserPermission] = useState<BrowserNotificationState>("checking");
  const [cameraCapability, setCameraCapability] = useState<"checking" | "supported" | "unsupported">("checking");
  const [selectedItemId, setSelectedItemId] = useState("");
  const [actionState, setActionState] = useState<NotificationActionState>({});

  const refreshNotifications = useCallback(async () => {
    await Promise.all([
      loadCaregiverInto(setAfferens, getAfferensStatus),
      loadCaregiverInto(setRuntime, getActionRuntimeStatus),
      loadCaregiverInto(setActionEvents, () => getActionEvents({ date: todayDate, limit: 20 })),
      loadCaregiverInto(setWellnessChecks, () => getWellnessChecks(todayDate)),
      loadCaregiverInto(setHydration, () => getHydrationSummary(todayDate)),
      loadCaregiverInto(setFamilyMessages, () => getFamilyMessages(false)),
      loadCaregiverInto(setTasks, getTasks),
      loadCaregiverInto(setAlerts, getAlerts)
    ]);
  }, [todayDate]);

  useEffect(() => {
    void refreshNotifications();
    const timer = window.setInterval(() => {
      void refreshNotifications();
    }, NOTIFICATION_POLL_MS);

    return () => window.clearInterval(timer);
  }, [refreshNotifications]);

  useEffect(() => {
    if (typeof window === "undefined" || !("Notification" in window)) {
      setBrowserPermission("unsupported");
    } else {
      setBrowserPermission(window.Notification.permission);
    }

    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setCameraCapability("unsupported");
    } else {
      setCameraCapability("supported");
    }
  }, []);

  const queueItems = useMemo(
    () =>
      buildCaregiverQueue({
        actionEvents: actionEvents.data?.events ?? [],
        alerts: alerts.data?.alerts ?? [],
        familyMessages: familyMessages.data?.messages ?? [],
        hydration: hydration.data,
        tasks: tasks.data?.tasks ?? [],
        wellnessChecks: wellnessChecks.data?.checks ?? []
      }),
    [
      actionEvents.data?.events,
      alerts.data?.alerts,
      familyMessages.data?.messages,
      hydration.data,
      tasks.data?.tasks,
      wellnessChecks.data?.checks
    ]
  );
  const selectedItem = queueItems.find((item) => item.id === selectedItemId) ?? queueItems[0] ?? null;
  const readiness = summarizeActionReadiness(afferens, runtime, cameraCapability);
  const canActuate = Boolean(selectedItem?.taskId && selectedItem.evidenceIds.length);
  const canCapture = Boolean(canActuate && afferens.data?.source_node_id);

  useEffect(() => {
    if (!selectedItemId && queueItems[0]) {
      setSelectedItemId(queueItems[0].id);
    }
  }, [queueItems, selectedItemId]);

  async function handleRequestNotifications() {
    if (typeof window === "undefined" || !("Notification" in window)) {
      setBrowserPermission("unsupported");
      return;
    }
    setActionState({ loading: "notify" });
    try {
      const permission = await window.Notification.requestPermission();
      setBrowserPermission(permission);
      setActionState({
        tone: permission === "granted" ? "success" : undefined,
        title: permission === "granted" ? "Browser notifications allowed" : "Browser notifications not enabled",
        body:
          permission === "granted"
            ? "This browser can show local caregiver reminders while the page is open."
            : "The queue still works in the page. You can change browser permissions later."
      });
    } catch (error) {
      setActionState(errorActionState(error, "Browser notification permission could not be requested."));
    }
  }

  async function handleSendLocalNotification() {
    if (!selectedItem || typeof window === "undefined" || !("Notification" in window) || window.Notification.permission !== "granted") {
      return;
    }
    setActionState({ loading: "notify" });
    new window.Notification(selectedItem.title, {
      body: selectedItem.body,
      tag: selectedItem.id
    });
    setActionState({
      tone: "success",
      title: "Local reminder shown",
      body: "The browser notification used the selected queue item. It is only a local caregiver reminder."
    });
  }

  async function handleAcknowledge(item: CaregiverQueueItem) {
    setActionState({ loading: "ack" });
    try {
      if (item.wellnessCheckId) {
        await acknowledgeWellnessCheck(item.wellnessCheckId, {
          acknowledged_by: "caregiver",
          note: "Caregiver acknowledged from the notification queue."
        });
      } else if (item.familyMessageId) {
        await acknowledgeFamilyMessage(item.familyMessageId);
      } else if (item.alertId) {
        await acknowledgeAlert(item.alertId, "Caregiver is checking this from the notification queue.");
      } else {
        setActionState({
          title: "No acknowledgement endpoint",
          body: "This item is informational. Use live verification or the detailed review panel when available."
        });
        return;
      }
      setActionState({
        tone: "success",
        title: "Acknowledgement recorded",
        body: "The queue will refresh with the latest caregiver state."
      });
      await refreshNotifications();
    } catch (error) {
      setActionState(errorActionState(error, "Acknowledgement could not be recorded."));
    }
  }

  async function handleVerify(item: CaregiverQueueItem) {
    if (!item.taskId) {
      setActionState({
        title: "Live verification needs a task",
        body: "This queue item does not expose a task ID yet, so use acknowledgement or detailed review."
      });
      return;
    }
    setActionState({ loading: "verify" });
    try {
      const response = await verifyTask(item.taskId);
      setActionState({
        tone: response.verification.state === "verified" ? "success" : undefined,
        title: `Live verification ${sentenceCase(response.verification.state)}`,
        body: response.verification.message
      });
      await refreshNotifications();
    } catch (error) {
      setActionState(errorActionState(error, "Live verification could not run."));
    }
  }

  async function handleAlarm(item: CaregiverQueueItem | null) {
    if (!item || !canActuate) {
      setActionState({
        title: "Actuation requires linked evidence",
        body: "Select a queue item with live evidence and a task before sending a safe command."
      });
      return;
    }
    setActionState({ loading: "alarm" });
    try {
      const response = await triggerAssistiveAlarm({
        reason: item.kind,
        severity: item.severity,
        taskId: item.taskId
      });
      setActionState(actuationState(response));
      await refreshNotifications();
    } catch (error) {
      setActionState(errorActionState(error, "Assistive alarm command could not be sent."));
    }
  }

  async function handleCapture(item: CaregiverQueueItem | null) {
    if (!item || !canCapture) {
      setActionState({
        title: "Capture requires a live node and linked task",
        body: "Select a queue item with evidence and wait for Afferens to report a live source node."
      });
      return;
    }
    setActionState({ loading: "capture" });
    try {
      const response = await captureFrameForTask({
        taskId: item.taskId,
        targetNodeId: afferens.data?.source_node_id
      });
      setActionState(actuationState(response));
      await refreshNotifications();
    } catch (error) {
      setActionState(errorActionState(error, "Capture-frame command could not be sent."));
    }
  }

  return (
    <section className="action-notification-center" aria-labelledby="action-notifications-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Caregiver Review</p>
          <h1 id="action-notifications-title">Action notifications</h1>
          <p>Review possible action candidates, gentle prompts, unresolved searches, and evidence-linked assistive commands.</p>
        </div>
        <button className="button button--secondary" onClick={() => void refreshNotifications()} type="button">
          Refresh queue
        </button>
      </div>

      <div className="action-readiness-strip" aria-label="Action readiness summary">
        <CaregiverMetric title="Action Node" value={readiness.label} tone={readiness.tone} detail={readiness.body} />
        <CaregiverMetric
          title="Live Afferens"
          value={afferens.data?.state === "live" ? "Live node" : afferens.loading ? "Checking" : "No live node"}
          tone={afferens.data?.state === "live" ? "good" : afferens.data?.state === "no_live_events" ? "warn" : "quiet"}
          detail={afferens.data?.message || afferens.error || "Use the official Afferens node setup first."}
        />
        <CaregiverMetric
          title="Browser notifications"
          value={notificationLabel(browserPermission)}
          tone={notificationTone(browserPermission)}
          detail={notificationCopy(browserPermission)}
        />
        <CaregiverMetric
          title="Queue"
          value={`${queueItems.length} items`}
          tone={queueItems.length ? "warn" : "good"}
          detail={queueItems.length ? "Caregiver review is waiting." : "No notification items are open."}
        />
      </div>

      <div className="action-notification-actions">
        <button
          className="button button--secondary"
          disabled={browserPermission === "unsupported" || browserPermission === "granted" || actionState.loading === "notify"}
          onClick={() => void handleRequestNotifications()}
          type="button"
        >
          {browserPermission === "granted" ? "Notifications allowed" : "Allow browser notices"}
        </button>
        <button
          className="button button--secondary"
          disabled={browserPermission !== "granted" || !selectedItem || actionState.loading === "notify"}
          onClick={() => void handleSendLocalNotification()}
          type="button"
        >
          Send local reminder
        </button>
      </div>

      {actionState.title ? (
        <StateBlock
          tone={actionState.tone === "error" ? "error" : actionState.tone === "success" ? "success" : "empty"}
          title={actionState.title}
          body={actionState.body || "The queue action finished."}
        />
      ) : null}

      <div className="action-notification-grid">
        <section className="action-queue-panel" aria-labelledby="action-queue-title">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Notification Queue</p>
              <h2 id="action-queue-title">Caregiver review items</h2>
            </div>
            <StatusPill label={queueItems.length ? "Review" : "Quiet"} tone={queueItems.length ? "warn" : "good"} />
          </div>

          {queueItems.length ? (
            <div className="action-queue-list">
              {queueItems.map((item) => (
                <article className="action-queue-row" key={item.id}>
                  <label>
                    <input
                      checked={selectedItem?.id === item.id}
                      onChange={() => setSelectedItemId(item.id)}
                      type="radio"
                    />
                    <span>{queueKindLabel(item.kind)}</span>
                  </label>
                  <div>
                    <div className="row-heading">
                      <h3>{item.title}</h3>
                      <StatusPill label={sentenceCase(item.severity)} tone={severityTone(item.severity)} />
                    </div>
                    <p>{item.body}</p>
                    <small>
                      {item.occurredAt ? formatDateTime(item.occurredAt) : "No time reported"}
                      {item.evidenceIds.length ? `, ${item.evidenceIds.length} evidence ref${item.evidenceIds.length === 1 ? "" : "s"}` : ", evidence not linked yet"}
                    </small>
                  </div>
                  <div className="task-actions">
                    <button
                      className="button button--secondary"
                      disabled={actionState.loading === "ack" || (!item.wellnessCheckId && !item.familyMessageId && !item.alertId)}
                      onClick={() => void handleAcknowledge(item)}
                      type="button"
                    >
                      {actionState.loading === "ack" ? "Saving" : "Acknowledge"}
                    </button>
                    <button
                      className="button button--secondary"
                      disabled={actionState.loading === "verify" || !item.taskId}
                      onClick={() => void handleVerify(item)}
                      type="button"
                    >
                      {actionState.loading === "verify" ? "Verifying" : "Verify live"}
                    </button>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <StateBlock title="No notification items" body="Possible fall checks, hydration prompts, family prompts, unresolved recovery tasks, and actuation verification items will appear here." />
          )}
        </section>

        <section className="action-actuation-panel" aria-labelledby="action-actuation-title">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Safe Actuation</p>
              <h2 id="action-actuation-title">Evidence-linked commands</h2>
            </div>
            <StatusPill label={canActuate ? "Evidence linked" : "Disabled"} tone={canActuate ? "warn" : "quiet"} />
          </div>
          <p>
            Afferens commands are disabled by default on the backend. This UI only enables a command after a selected queue item has live evidence and a task ID.
          </p>
          <dl className="compact-meta compact-meta--two">
            <div>
              <dt>Selected item</dt>
              <dd>{selectedItem?.title || "None"}</dd>
            </div>
            <div>
              <dt>Task</dt>
              <dd>{selectedItem?.taskId || "Required"}</dd>
            </div>
            <div>
              <dt>Evidence</dt>
              <dd>{selectedItem?.evidenceIds.length || 0}</dd>
            </div>
            <div>
              <dt>Target node</dt>
              <dd>{afferens.data?.source_node_id || "Waiting for live node"}</dd>
            </div>
          </dl>
          <div className="action-notification-actions">
            <button
              className="button button--secondary"
              disabled={!canActuate || actionState.loading === "alarm"}
              onClick={() => void handleAlarm(selectedItem)}
              type="button"
            >
              {actionState.loading === "alarm" ? "Sending" : "Try assistive alarm"}
            </button>
            <button
              className="button button--secondary"
              disabled={!canCapture || actionState.loading === "capture"}
              onClick={() => void handleCapture(selectedItem)}
              type="button"
            >
              {actionState.loading === "capture" ? "Requesting" : "Request capture frame"}
            </button>
          </div>
          {!canActuate ? (
            <StateBlock title="Actuation held" body="Select an unresolved evidence-backed task before trying a safe command. Alert-only items stay in review until linked to a task or backend alert actuation is exposed." />
          ) : null}
          <StateBlock title="Resolution still needs verification" body="A command attempt does not resolve the item. Use later live verification or a human acknowledgement before closing it." />
        </section>
      </div>
    </section>
  );
}

function CaregiverMetric({
  detail,
  title,
  tone,
  value
}: {
  detail: string;
  title: string;
  tone: StatusTone;
  value: string;
}) {
  return (
    <div className="connection-tile">
      <span>{title}</span>
      <strong>{value}</strong>
      <p>{detail}</p>
      <StatusPill label={metricToneLabel(tone)} tone={tone} />
    </div>
  );
}

function buildCaregiverQueue({
  actionEvents,
  alerts,
  familyMessages,
  hydration,
  tasks,
  wellnessChecks
}: {
  actionEvents: ActionEvent[];
  alerts: Alert[];
  familyMessages: FamilyMessage[];
  hydration?: HydrationSummaryResponse;
  tasks: Task[];
  wellnessChecks: WellnessCheck[];
}): CaregiverQueueItem[] {
  const taskById = new Map(tasks.map((task) => [task.id, task]));
  const fallCheckActionEventIds = linkedFallCheckActionEventIds(wellnessChecks);
  const items: CaregiverQueueItem[] = [];

  wellnessChecks
    .filter((check) => check.status === "open")
    .forEach((check) => {
      items.push({
        body: wellnessQueueBody(check),
        evidenceIds: check.evidence_ids ?? [],
        id: `wellness:${check.id}`,
        kind: check.type === "possible_fall_check" ? "possible_fall" : "hydration_prompt",
        occurredAt: check.occurred_at,
        severity: normalizeSeverity(check.severity),
        title: wellnessQueueTitle(check),
        wellnessCheckId: check.id
      });
    });

  if (hydration?.summary.status === "consider_prompting" && !items.some((item) => item.kind === "hydration_prompt")) {
    items.push({
      body: hydration.summary.message || "Hydration may be worth a calm caregiver prompt. The queue cannot infer intake from bottle or cup visibility alone.",
      evidenceIds: hydration.summary.evidence_ids ?? [],
      id: `hydration:${hydration.date}`,
      kind: "hydration_prompt",
      occurredAt: hydration.summary.latest_event_at,
      severity: "low",
      title: "Hydration prompt candidate"
    });
  }

  familyMessages
    .filter((message) => message.status !== "acknowledged")
    .forEach((message) => {
      items.push({
        body: message.body,
        evidenceIds: [],
        familyMessageId: message.id,
        id: `family:${message.id}`,
        kind: "family_prompt",
        occurredAt: message.starts_at,
        severity: message.priority === "high" ? "medium" : "low",
        title: message.title
      });
    });

  tasks
    .filter((task) => task.type === "object_recovery" && !["verified_resolved", "dismissed"].includes(task.state))
    .forEach((task) => {
      items.push({
        body: task.body || "An object recovery task is still unresolved.",
        evidenceIds: task.evidence_observation_ids ?? [],
        id: `task:${task.id}`,
        kind: "recovery_task",
        occurredAt: task.updated_at,
        severity: task.state === "failed_verification" ? "medium" : "low",
        taskId: task.id,
        title: task.title || "Unresolved recovery task"
      });
    });

  alerts
    .filter((alert) => alert.status === "open")
    .forEach((alert) => {
      const linkedTask = alert.task_id ? taskById.get(alert.task_id) : undefined;
      items.push({
        alertId: alert.id,
        body: alert.body || "A caregiver alert requires acknowledgement or later live verification.",
        evidenceIds: alert.evidence_observation_ids ?? linkedTask?.evidence_observation_ids ?? [],
        id: `alert:${alert.id}`,
        kind: "actuation_verification",
        occurredAt: alert.created_at,
        severity: normalizeSeverity(alert.severity),
        taskId: alert.task_id ?? linkedTask?.id,
        title: alert.title || "Actuation verification required"
      });
    });

  actionEvents
    .filter((event) => event.type === "fall_candidate" || event.type === "fall_escalated" || event.type === "drink_candidate")
    .filter((event) => event.type === "drink_candidate" || !fallCheckActionEventIds.has(event.id))
    .slice(0, 4)
    .forEach((event) => {
      items.push({
        actionEventId: event.id,
        body: actionEventQueueBody(event),
        evidenceIds: event.evidence_ids ?? [],
        id: `action:${event.id}`,
        kind: event.type === "drink_candidate" ? "hydration_prompt" : "possible_fall",
        occurredAt: event.occurred_at,
        severity: event.type === "fall_escalated" ? "medium" : "low",
        title: event.type === "drink_candidate" ? "Possible drink-action candidate" : "Possible fall candidate"
      });
    });

  return items
    .filter((item, index, list) => list.findIndex((candidate) => candidate.id === item.id) === index)
    .sort((left, right) => severityRank(right.severity) - severityRank(left.severity));
}

function summarizeActionReadiness(
  afferens: Loadable<AfferensStatus>,
  runtime: Loadable<ActionRuntimeStatusResponse>,
  cameraCapability: "checking" | "supported" | "unsupported"
): { body: string; label: string; tone: StatusTone } {
  if (afferens.data?.state === "no_live_events") {
    return {
      body: "No live Afferens node is active. Start the official node flow before diagnosing camera or model runtime.",
      label: "No live node",
      tone: "warn"
    };
  }
  if (cameraCapability === "unsupported") {
    return {
      body: "This browser does not expose camera access, so the browser Action Node cannot be the happy path here.",
      label: "Camera missing",
      tone: "bad"
    };
  }
  if (runtime.error) {
    return {
      body: "Action runtime status is unavailable. Manual telemetry remains only an unavailable-state fallback.",
      label: "Provider missing",
      tone: "warn"
    };
  }
  const drinkReady = runtime.data?.drink?.available;
  const fallReady = runtime.data?.fall?.available && runtime.data.fall.enabled !== false;
  if (drinkReady && fallReady) {
    return {
      body: "Browser drink telemetry and backend fall runtime report ready. Physical smoke still needs live verification.",
      label: "Ready",
      tone: "good"
    };
  }
  if (drinkReady || fallReady) {
    return {
      body: "One action path is ready and another is degraded. Candidate creation stays gated by available evidence.",
      label: "Degraded",
      tone: "warn"
    };
  }
  if (runtime.data?.fall && !runtime.data.fall.model_path_configured) {
    return {
      body: runtime.data.fall.message || "YOLO fall model path is not configured, so possible-fall frame analysis stays unavailable.",
      label: "Model missing",
      tone: "warn"
    };
  }
  if (runtime.loading) {
    return {
      body: "Checking browser Action Node and backend model readiness.",
      label: "Checking",
      tone: "info"
    };
  }
  return {
    body: "Action inference is not ready. Manual fallback can only save inconclusive unavailable-state reviews.",
    label: "Manual fallback",
    tone: "quiet"
  };
}

function actuationState(response: ActuationResponse): NotificationActionState {
  return {
    tone: response.ok ? "success" : "error",
    title: `Actuation ${sentenceCase(response.attempt.state)}`,
    body: response.attempt.message
  };
}

function actionEventQueueBody(event: ActionEvent): string {
  if (event.type === "drink_candidate") {
    return "This may indicate a drink action. Bottle or cup visibility alone is only context and not confirmed hydration.";
  }
  return "This notification has been escalated to the caregiver for a possible fall.";
}

function linkedFallCheckActionEventIds(wellnessChecks: WellnessCheck[]): Set<string> {
  return new Set(
    wellnessChecks
      .filter((check) => check.type === "possible_fall_check")
      .map((check) => {
        const actionEventId = check.metadata?.action_event_id;
        return typeof actionEventId === "string" ? actionEventId : null;
      })
      .filter((id): id is string => Boolean(id))
  );
}

function errorActionState(error: unknown, fallback: string): NotificationActionState {
  return {
    body: error instanceof Error ? error.message : fallback,
    title: "Action failed",
    tone: "error"
  };
}

function metricToneLabel(tone: StatusTone): string {
  if (tone === "good") {
    return "Ready";
  }
  if (tone === "bad") {
    return "Unavailable";
  }
  if (tone === "warn") {
    return "Check";
  }
  if (tone === "info") {
    return "Review";
  }
  return "Quiet";
}

function notificationLabel(permission: BrowserNotificationState): string {
  if (permission === "unsupported") {
    return "Unsupported";
  }
  if (permission === "granted") {
    return "Allowed";
  }
  if (permission === "denied") {
    return "Denied";
  }
  if (permission === "default") {
    return "Optional";
  }
  return "Checking";
}

function notificationCopy(permission: BrowserNotificationState): string {
  if (permission === "unsupported") {
    return "This browser does not support local Notification API reminders.";
  }
  if (permission === "granted") {
    return "Local reminders can appear while this caregiver page is open.";
  }
  if (permission === "denied") {
    return "The in-page queue remains available. Browser settings can change this later.";
  }
  return "Optional local reminders are available without adding dependencies.";
}

function notificationTone(permission: BrowserNotificationState): StatusTone {
  if (permission === "granted") {
    return "good";
  }
  if (permission === "denied") {
    return "quiet";
  }
  if (permission === "unsupported") {
    return "quiet";
  }
  return "info";
}

function normalizeSeverity(severity: string): "low" | "medium" | "high" {
  if (severity === "high" || severity === "medium") {
    return severity;
  }
  return "low";
}

function queueKindLabel(kind: QueueItemKind): string {
  if (kind === "possible_fall") {
    return "Possible fall check";
  }
  if (kind === "hydration_prompt") {
    return "Hydration prompt";
  }
  if (kind === "family_prompt") {
    return "Family prompt";
  }
  if (kind === "recovery_task") {
    return "Recovery task";
  }
  return "Actuation verification";
}

function severityRank(severity: "low" | "medium" | "high"): number {
  if (severity === "high") {
    return 3;
  }
  if (severity === "medium") {
    return 2;
  }
  return 1;
}

function severityTone(severity: "low" | "medium" | "high"): StatusTone {
  if (severity === "high") {
    return "bad";
  }
  if (severity === "medium") {
    return "warn";
  }
  return "info";
}

function wellnessQueueBody(check: WellnessCheck): string {
  if (check.type === "possible_fall_check") {
    return "This notification has been escalated to the caregiver for a possible fall.";
  }
  if (check.type === "hydration_prompt") {
    return `${check.body} Do not treat nearby bottle or cup visibility as confirmed drinking.`;
  }
  return check.body;
}

function wellnessQueueTitle(check: WellnessCheck): string {
  if (check.type === "possible_fall_check") {
    return "Possible fall candidate";
  }
  if (check.type === "hydration_prompt") {
    return "Hydration prompt candidate";
  }
  return check.title;
}

async function loadCaregiverInto<T>(
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
