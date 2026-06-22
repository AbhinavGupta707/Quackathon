"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  evaluateDrinkActionTelemetry,
  getActionEvents,
  getLatestObservation,
  getActionRuntimeStatus,
  inferFallFromFrame,
  isUnavailableEndpoint,
  recordActionEvent
} from "@/lib/api";
import {
  browserCameraSupported,
  type CameraState,
  type MediaPipeRuntimeState,
  useBrowserActionRuntime
} from "@/lib/useBrowserActionRuntime";
import { formatDateTime, sentenceCase } from "@/lib/format";
import type {
  ActionEvent,
  ActionEventsResponse,
  ActionEventType,
  ActionRuntimeStatusResponse,
  ActionTelemetryEvaluateResponse,
  LatestObservationResponse,
  Loadable
} from "@/lib/types";
import { EvidenceRefs } from "./EvidenceRefs";
import { StateBlock } from "./StateBlock";
import { StatusPill, type StatusTone } from "./StatusPill";

const POLL_MS = 15000;
const AUTO_DRINK_COOLDOWN_MS = 30000;
const AUTO_FALL_SCAN_MS = 1800;
const AUTO_FALL_EVENT_COOLDOWN_MS = 30000;
const DRINK_CONTEXT_OBJECTS = new Set([
  "bottle",
  "cup",
  "glass",
  "mug",
  "water",
  "water_bottle",
  "sports_bottle",
  "drinking_glass"
]);

type ActionMessage = {
  body: string;
  title: string;
  tone?: "error" | "success";
};

export function CaregiverActionReviewClient() {
  const selectedDate = useMemo(() => toDateInputValue(new Date()), []);
  const selectedType: ActionEventType | "" = "";
  const [events, setEvents] = useState<Loadable<ActionEventsResponse>>({ loading: true });
  const [nodeId, setNodeId] = useState("BROWSER-ACTION-NODE");
  const [zoneId, setZoneId] = useState("");
  const [evidenceText, setEvidenceText] = useState("");
  const [runtimeStatus, setRuntimeStatus] = useState<Loadable<ActionRuntimeStatusResponse>>({
    loading: true
  });
  const [latestObservation, setLatestObservation] = useState<Loadable<LatestObservationResponse>>({
    loading: true
  });
  const [message, setMessage] = useState<ActionMessage | null>(null);
  const [autoMonitorEnabled, setAutoMonitorEnabled] = useState(true);
  const [pending, setPending] = useState<"drink" | "fall" | "record_inconclusive" | null>(null);
  const autoDrinkBusyRef = useRef(false);
  const autoFallBusyRef = useRef(false);
  const evaluateDrinkRef = useRef<((options?: { automatic?: boolean }) => Promise<void>) | null>(null);
  const evaluateFallRef = useRef<((options?: { automatic?: boolean }) => Promise<void>) | null>(null);
  const lastAutoDrinkAtRef = useRef(0);
  const lastAutoFallEventAtRef = useRef(0);
  const actionRuntime = useBrowserActionRuntime();
  const { setDrinkObjectContext } = actionRuntime;

  const refreshEvents = useCallback(async () => {
    await loadInto(setEvents, () =>
      getActionEvents({ date: selectedDate, limit: 30, type: selectedType })
    );
  }, [selectedDate, selectedType]);

  useEffect(() => {
    void refreshEvents();
    const timer = window.setInterval(() => {
      void refreshEvents();
    }, POLL_MS);

    return () => window.clearInterval(timer);
  }, [refreshEvents]);

  const refreshRuntimeStatus = useCallback(async () => {
    await loadInto(setRuntimeStatus, getActionRuntimeStatus);
  }, []);

  useEffect(() => {
    void refreshRuntimeStatus();
  }, [refreshRuntimeStatus]);

  const refreshLatestObservation = useCallback(async () => {
    await loadInto(setLatestObservation, getLatestObservation);
  }, []);

  useEffect(() => {
    void refreshLatestObservation();
    const timer = window.setInterval(() => {
      void refreshLatestObservation();
    }, 5000);

    return () => window.clearInterval(timer);
  }, [refreshLatestObservation]);

  const drinkContext = useMemo(
    () => readDrinkContext(latestObservation.data),
    [latestObservation.data]
  );
  const cupOrBottleContext = drinkContext.available;

  const evidenceIds = useMemo(() => {
    const typedEvidenceIds = evidenceText
      .split(",")
      .map((id) => id.trim())
      .filter(Boolean);
    if (typedEvidenceIds.length) {
      return typedEvidenceIds;
    }
    return drinkContext.evidenceIds;
  }, [drinkContext.evidenceIds, evidenceText]);
  const drinkDisabledReason = drinkSubmissionDisabledReason(
    cupOrBottleContext,
    actionRuntime.mediaPipeState,
    actionRuntime.metrics
  );

  useEffect(() => {
    setDrinkObjectContext(cupOrBottleContext);
  }, [setDrinkObjectContext, cupOrBottleContext]);

  async function handleStartCamera() {
    if (!browserCameraSupported()) {
      setMessage({
        title: "Camera unavailable",
        body: "This browser does not expose webcam access. The fallback controls remain available for backend testing only."
      });
      return;
    }

    setMessage(null);
    const result = await actionRuntime.start();
    if (result.ok) {
      setMessage({
        tone: "success",
        title: "Action Node started",
        body: "The live preview is local. Drink candidates and fall frame scans now run automatically while monitoring is on."
      });
    } else {
      setMessage({
        tone: "error",
        title: actionRuntime.cameraState === "blocked" ? "Camera permission needed" : "Action Node unavailable",
        body: result.message || "Allow camera access, or use fallback controls only for unavailable-state testing."
      });
    }
  }

  function handleStopCamera() {
    actionRuntime.stop();
  }

  async function handleEvaluateDrink({ automatic = false }: { automatic?: boolean } = {}) {
    if (automatic) {
      if (autoDrinkBusyRef.current) {
        return;
      }
      autoDrinkBusyRef.current = true;
    } else {
      setPending("drink");
      setMessage(null);
    }
    try {
      const payload = actionRuntime.buildDrinkTelemetry({
        cupOrBottleContext,
        evidenceIds,
        nodeId,
        objectKeys: drinkContext.objectKeys,
        zoneId: optionalValue(zoneId)
      });
      if (!payload) {
        if (!automatic) {
          setMessage({
            title: "Drink action not ready",
            body:
              drinkDisabledReason ||
              "MediaPipe has not yet seen object context plus hand approach, mouth dwell, and exit. Cup or bottle visibility by itself is only context."
          });
        }
        return;
      }
      const response = await evaluateDrinkActionTelemetry(payload);
      lastAutoDrinkAtRef.current = Date.now();
      setMessage(successMessage(response, automatic ? "Drink event logged automatically" : "Drink-action telemetry reviewed"));
      await refreshEvents();
    } catch (error) {
      if (isUnavailable(error)) {
        if (!automatic) {
          await recordManualCandidate("action_inconclusive", "drink_candidate");
        }
      } else {
        if (!automatic) {
          setMessage(errorMessage(error, "Drink-action telemetry could not be evaluated."));
        }
      }
    } finally {
      if (automatic) {
        autoDrinkBusyRef.current = false;
      } else {
        setPending(null);
      }
    }
  }

  async function handleEvaluateFall({ automatic = false }: { automatic?: boolean } = {}) {
    if (automatic) {
      if (autoFallBusyRef.current) {
        return;
      }
      autoFallBusyRef.current = true;
    } else {
      setPending("fall");
      setMessage(null);
    }
    try {
      if (!fallRuntimeReady(runtimeStatus.data)) {
        if (!automatic) {
          setMessage({
            title: "Fall model unavailable",
            body: "The backend YOLO fall runtime is not reporting ready, so this screen will not create a synthetic possible-fall result."
          });
        }
        return;
      }

      const frame = await actionRuntime.captureFrame();
      if (!frame) {
        if (!automatic) {
          setMessage({
            title: "No current frame",
            body: "Start the Action Node camera before requesting backend fall analysis."
          });
        }
        return;
      }

      const response = await inferFallFromFrame({
        evidenceIds,
        frame,
        occurredAt: new Date().toISOString(),
        persistInconclusive: !automatic,
        sourceNodeId: nodeId,
        zoneId: optionalValue(zoneId)
      });
      if (response.decision === "fall_candidate" || response.decision === "fall_escalated") {
        lastAutoFallEventAtRef.current = Date.now();
        setMessage(successMessage(response, automatic ? "Possible fall event logged automatically" : "Possible fall frame reviewed"));
        await refreshEvents();
      } else if (!automatic) {
        setMessage(successMessage(response, "Fall frame reviewed"));
        await refreshEvents();
      }
    } catch (error) {
      if (!automatic) {
        setMessage(errorMessage(error, "Possible fall frame could not be evaluated."));
      }
    } finally {
      if (automatic) {
        autoFallBusyRef.current = false;
      } else {
        setPending(null);
      }
    }
  }

  async function recordManualCandidate(type: ActionEventType, attemptedType?: ActionEventType) {
    const isDrink = attemptedType === "drink_candidate" || type === "drink_candidate";
    setPending("record_inconclusive");
    setMessage(null);
    try {
      const response = await recordActionEvent({
        type,
        occurred_at: new Date().toISOString(),
        confidence: "low",
        score: type === "action_inconclusive" ? undefined : isDrink ? 0.62 : 0.66,
        source: "browser_manual_test",
        source_node_id: nodeId,
        zone_id: optionalValue(zoneId),
        evidence_ids: evidenceIds,
        metadata: {
          raw_video_stored: false,
          raw_frames_sent: false,
          third_party_frames_sent: false,
          adapter_version: "browser_action_node_v1",
          requires_caregiver_confirmation: true,
          attempted_type: attemptedType,
          object_visibility_is_context_only: isDrink,
          fallback_reason:
            type === "action_inconclusive"
              ? "Runtime unavailable; saved inconclusive review instead of bypassing action gate."
              : "Runtime unavailable; recorded compact manual telemetry."
        }
      });
      setMessage(
        successMessage(
          response,
          type === "action_inconclusive"
            ? "Evaluator unavailable; inconclusive review saved"
            : "Manual action candidate recorded"
        )
      );
      await refreshEvents();
    } catch (recordError) {
      setMessage(
        errorMessage(
          recordError,
          "Action-event endpoints are not available yet. The local Action Node can still preview the camera without storing video."
        )
      );
    } finally {
      setPending(null);
    }
  }

  async function handleRecordInconclusive(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending("record_inconclusive");
    setMessage(null);
    try {
      const response = await recordActionEvent({
        type: "action_inconclusive",
        occurred_at: new Date().toISOString(),
        confidence: "low",
        source: "browser_action_node",
        source_node_id: nodeId,
        zone_id: optionalValue(zoneId),
        evidence_ids: evidenceIds,
        metadata: {
          raw_video_stored: false,
          raw_frames_sent: false,
          third_party_frames_sent: false,
          reason: "caregiver_requested_review_without_enough_action_signal"
        }
      });
      setMessage(successMessage(response, "Inconclusive action review saved"));
      await refreshEvents();
    } catch (error) {
      setMessage(errorMessage(error, "Action-event recording is not available yet."));
    } finally {
      setPending(null);
    }
  }

  useEffect(() => {
    evaluateDrinkRef.current = handleEvaluateDrink;
    evaluateFallRef.current = handleEvaluateFall;
  });

  useEffect(() => {
    if (
      !autoMonitorEnabled ||
      pending ||
      !cupOrBottleContext ||
      !drinkRuntimeCanSubmit(actionRuntime.mediaPipeState, actionRuntime.metrics) ||
      !actionRuntime.metrics.drinkCandidateReady
    ) {
      return;
    }
    if (Date.now() - lastAutoDrinkAtRef.current < AUTO_DRINK_COOLDOWN_MS) {
      return;
    }

    void evaluateDrinkRef.current?.({ automatic: true });
  }, [
    actionRuntime.mediaPipeState,
    actionRuntime.metrics,
    autoMonitorEnabled,
    cupOrBottleContext,
    pending
  ]);

  useEffect(() => {
    if (
      !autoMonitorEnabled ||
      actionRuntime.cameraState !== "on" ||
      !fallRuntimeReady(runtimeStatus.data)
    ) {
      return;
    }

    const timer = window.setInterval(() => {
      if (Date.now() - lastAutoFallEventAtRef.current < AUTO_FALL_EVENT_COOLDOWN_MS) {
        return;
      }
      void evaluateFallRef.current?.({ automatic: true });
    }, AUTO_FALL_SCAN_MS);

    return () => window.clearInterval(timer);
  }, [actionRuntime.cameraState, autoMonitorEnabled, runtimeStatus.data]);

  const endpointUnavailable = events.error;

  return (
    <section className="caregiver-action-review" aria-labelledby="action-review-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Action Intelligence</p>
          <h2 id="action-review-title">Live webcam monitor</h2>
          <p>Start the camera. Drink and possible-fall events are created automatically when the runtime has enough signal.</p>
        </div>
        <button className="button button--secondary" onClick={() => void refreshEvents()} type="button">
          Refresh events
        </button>
      </div>

      {message ? (
        <StateBlock
          tone={message.tone === "error" ? "error" : message.tone === "success" ? "success" : "empty"}
          title={message.title}
          body={message.body}
        />
      ) : null}

      {endpointUnavailable ? (
        <StateBlock
          title="Action-event endpoints unavailable"
          body="The Action Node can still run a local camera preview, but event review will appear here when backend action-event endpoints are available."
        />
      ) : null}

      <div className="action-review-grid">
        <section className="review-card action-node-card" aria-labelledby="action-node-title">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Browser Action Node</p>
              <h2 id="action-node-title">Laptop or external webcam</h2>
            </div>
            <StatusPill label={cameraLabel(actionRuntime.cameraState)} tone={cameraTone(actionRuntime.cameraState)} />
          </div>

          <div className="action-camera-frame">
            <video aria-label="Local Action Node camera preview" muted playsInline ref={actionRuntime.videoRef} />
            {actionRuntime.cameraState !== "on" ? (
              <div className="action-camera-empty">
                <strong>{actionRuntime.cameraState === "unsupported" ? "Camera API unavailable" : "Preview off"}</strong>
                <p>Start the local Action Node to run browser pose and hand inference.</p>
              </div>
            ) : null}
          </div>

          <div className="action-node-controls">
            <button className="button button--primary" disabled={actionRuntime.cameraState === "starting" || actionRuntime.cameraState === "on"} onClick={() => void handleStartCamera()} type="button">
              {actionRuntime.cameraState === "on"
                ? "Camera running"
                : actionRuntime.cameraState === "starting"
                  ? "Starting camera"
                  : "Start Action Node camera"}
            </button>
            <button className="button button--secondary" disabled={actionRuntime.cameraState !== "on"} onClick={handleStopCamera} type="button">
              Stop camera
            </button>
          </div>

          <label className="action-checkbox-label action-auto-toggle">
            <input
              checked={autoMonitorEnabled}
              onChange={(event) => setAutoMonitorEnabled(event.target.checked)}
              type="checkbox"
            />
            Automatic drink and fall monitoring
          </label>

          <div className="action-runtime-status-grid">
            <RuntimeStatusCard
              body={mediaPipeStatusCopy(actionRuntime.mediaPipeState, actionRuntime.metrics)}
              label={mediaPipeStatusLabel(actionRuntime.mediaPipeState)}
              title="MediaPipe"
              tone={mediaPipeTone(actionRuntime.mediaPipeState)}
            />
            <RuntimeStatusCard
              body={handStatusCopy(actionRuntime.metrics)}
              label={handStatusLabel(actionRuntime.metrics)}
              title="Hand landmarks"
              tone={handStatusTone(actionRuntime.metrics)}
            />
            <RuntimeStatusCard
              body={fallStatusCopy(runtimeStatus)}
              label={fallStatusLabel(runtimeStatus)}
              title="YOLO backend"
              tone={fallStatusTone(runtimeStatus)}
            />
          </div>

          <div className="action-privacy-note">
            <strong>Privacy default</strong>
            <p>Raw video persistence is off. Drink inference runs locally in the browser; automatic fall monitoring sends current frames only to the local backend while the camera is on.</p>
          </div>

          <div className="action-test-card action-test-card--drink">
            <div>
              <p className="eyebrow">Water Test</p>
              <h3>Drinking motion</h3>
              <p>Show a cup, bottle, or water in the live Afferens view, then take a clear sip in the webcam view. The drink event logs automatically after both signals are present.</p>
            </div>
            <div className="action-context-row">
              <span>Live object context</span>
              <StatusPill
                label={drinkContext.available ? drinkContext.label : latestObservation.loading ? "Checking" : "Waiting"}
                tone={drinkContext.available ? "good" : latestObservation.loading ? "warn" : "quiet"}
              />
            </div>
            <small>{actionRuntime.metrics.drinkCandidateReady ? "Drink candidate is ready." : "Waiting for hand-to-mouth drink motion."}</small>
          </div>

          <div className="action-test-card action-test-card--fall">
            <div>
              <p className="eyebrow">Fall Test</p>
              <h3>Possible fall detection</h3>
              <p>Keep the test area in view. The app scans current frames automatically and only saves a possible-fall event after the model sees persistent fallen evidence.</p>
            </div>
            <small>{fallRuntimeReady(runtimeStatus.data) ? "YOLO fall runtime is ready." : "YOLO fall runtime is not ready yet."}</small>
          </div>

          {drinkDisabledReason ? (
            <StateBlock
              title="Drink monitoring waiting"
              body={drinkDisabledReason}
            />
          ) : null}

          <details className="action-diagnostic-panel">
            <summary>Advanced settings and runtime diagnostics</summary>
            <div className="action-telemetry-actions">
              <button
                className="button button--secondary"
                disabled={
                  pending === "drink" ||
                  !drinkRuntimeCanSubmit(actionRuntime.mediaPipeState, actionRuntime.metrics) ||
                  !cupOrBottleContext ||
                  !actionRuntime.metrics.drinkCandidateReady
                }
                onClick={() => void handleEvaluateDrink()}
                type="button"
              >
                {pending === "drink" ? "Sending drink event" : "Manually send drink event"}
              </button>
              <button
                className="button button--secondary"
                disabled={
                  pending === "fall" ||
                  actionRuntime.cameraState !== "on" ||
                  !fallRuntimeReady(runtimeStatus.data)
                }
                onClick={() => void handleEvaluateFall()}
                type="button"
              >
                {pending === "fall" ? "Checking frame" : "Manually check fall frame"}
              </button>
            </div>
            <div className="action-node-form">
              <label>
                Source node
                <input onChange={(event) => setNodeId(event.target.value)} type="text" value={nodeId} />
              </label>
              <label>
                Zone ID
                <input onChange={(event) => setZoneId(event.target.value)} placeholder="zone_living_room" type="text" value={zoneId} />
              </label>
              <label className="action-node-form__wide">
                Evidence IDs
                <input
                  onChange={(event) => setEvidenceText(event.target.value)}
                  placeholder="obs_01..., frame_ref_01..."
                  type="text"
                  value={evidenceText}
                />
              </label>
            </div>
            <dl className="compact-meta compact-meta--two action-runtime-metrics">
              <div>
                <dt>Pose frames</dt>
                <dd>{actionRuntime.metrics.framesAnalyzed}</dd>
              </div>
              <div>
                <dt>Pose visible</dt>
                <dd>{actionRuntime.metrics.poseVisible ? "Yes" : "Not yet"}</dd>
              </div>
              <div>
                <dt>Hand visible</dt>
                <dd>{actionRuntime.metrics.handVisible ? "Yes" : "Not yet"}</dd>
              </div>
              <div>
                <dt>Hydration stage</dt>
                <dd>{hydrationStageLabel(actionRuntime.metrics.hydrationFsmStage)}</dd>
              </div>
              <div>
                <dt>Dwell window</dt>
                <dd>{actionRuntime.metrics.signalWindowSeconds.toFixed(1)}s</dd>
              </div>
              <div>
                <dt>Drink candidate</dt>
                <dd>{actionRuntime.metrics.drinkCandidateReady ? "Fresh" : "Waiting"}</dd>
              </div>
            </dl>
            <dl className="compact-meta compact-meta--two">
              <div>
                <dt>Runtime mode</dt>
                <dd>{runtimeModeLabel(actionRuntime.metrics.runtimeMode)}</dd>
              </div>
              <div>
                <dt>Asset check</dt>
                <dd>{assetStatusLabel(actionRuntime.metrics.assetStatus)}</dd>
              </div>
              <div>
                <dt>Hand asset</dt>
                <dd>{assetStatusLabel(actionRuntime.metrics.handAssetStatus)}</dd>
              </div>
              <div>
                <dt>Sampling</dt>
                <dd>{actionRuntime.metrics.detectionIntervalMs}ms</dd>
              </div>
              <div>
                <dt>Slow frames</dt>
                <dd>{actionRuntime.metrics.slowFrameCount}</dd>
              </div>
              <div>
                <dt>Last pose</dt>
                <dd>{actionRuntime.metrics.lastPoseAt ? formatDateTime(actionRuntime.metrics.lastPoseAt) : "No fresh pose"}</dd>
              </div>
              <div>
                <dt>Last hand</dt>
                <dd>{actionRuntime.metrics.lastHandAt ? formatDateTime(actionRuntime.metrics.lastHandAt) : "No fresh hand"}</dd>
              </div>
              <div>
                <dt>Last frame</dt>
                <dd>{actionRuntime.metrics.lastFrameAt ? formatDateTime(actionRuntime.metrics.lastFrameAt) : "No frame yet"}</dd>
              </div>
            </dl>
          </details>

          {actionRuntime.metrics.lastError ? (
            <StateBlock
              tone="error"
              title="MediaPipe unavailable"
              body={actionRuntime.metrics.lastError}
            />
          ) : null}

          <details className="manual-action-fallback" aria-labelledby="manual-action-fallback-title">
            <summary>Fallback controls for unavailable-state testing</summary>
            <div>
              <h3 id="manual-action-fallback-title">Unavailable-state testing only</h3>
              <p>
                Use these controls only when MediaPipe or backend fall inference is unavailable. They do not replace real local action inference.
              </p>
            </div>
            <div className="action-telemetry-actions">
              <button
                className="button button--secondary"
                disabled={pending === "record_inconclusive"}
                onClick={() => void recordManualCandidate("action_inconclusive", "drink_candidate")}
                type="button"
              >
                Save drink inconclusive fallback
              </button>
              <button
                className="button button--secondary"
                disabled={pending === "record_inconclusive"}
                onClick={() => void recordManualCandidate("action_inconclusive", "fall_candidate")}
                type="button"
              >
                Save fall inconclusive fallback
              </button>
            </div>
            <form className="action-node-form" onSubmit={handleRecordInconclusive}>
              <button className="button button--secondary action-node-form__wide" disabled={pending === "record_inconclusive"} type="submit">
                {pending === "record_inconclusive" ? "Saving" : "Save caregiver-requested inconclusive review"}
              </button>
            </form>
          </details>
        </section>

        <ActionEventList events={events} />
      </div>
    </section>
  );
}

function ActionEventList({ events }: { events: Loadable<ActionEventsResponse> }) {
  const actionEvents = (events.data?.events ?? []).filter((event) => event.type !== "action_inconclusive");

  return (
    <section className="review-card" aria-labelledby="action-event-list-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Caregiver Review</p>
          <h2 id="action-event-list-title">Recent action candidates</h2>
        </div>
        <StatusPill
          label={events.loading ? "Checking" : events.error ? "Unavailable" : `${actionEvents.length} events`}
          tone={events.error ? "quiet" : actionEvents.length ? "info" : "quiet"}
        />
      </div>

      {events.loading && !events.data ? (
        <StateBlock tone="loading" title="Loading action events" body="Checking recent fall and drink-action candidates." />
      ) : events.error ? (
        <StateBlock
          title="No action-event review yet"
          body="This action-event endpoint is unavailable. Existing wellness and evidence review sections remain available."
        />
      ) : actionEvents.length ? (
        <div className="action-event-list">
          {actionEvents.map((event) => (
            <ActionEventRow event={event} key={event.id} />
          ))}
        </div>
      ) : (
        <StateBlock
          title="No action events for this view"
          body="Start the camera. Drink and possible-fall events will appear here automatically when detected."
        />
      )}
    </section>
  );
}

function readDrinkContext(data?: LatestObservationResponse): {
  available: boolean;
  evidenceIds: string[];
  label: string;
  objectKeys: string[];
} {
  const observation = data?.observation ?? null;
  if (!observation?.objects?.length) {
    return {
      available: false,
      evidenceIds: [],
      label: "Waiting",
      objectKeys: []
    };
  }

  const matches = observation.objects.filter((object) =>
    isDrinkContextObject(object.object_key) ||
    isDrinkContextObject(object.label) ||
    isDrinkContextObject(object.display_name)
  );

  if (!matches.length) {
    return {
      available: false,
      evidenceIds: observation.id ? [observation.id] : [],
      label: "No cup/water",
      objectKeys: []
    };
  }

  const objectKeys = Array.from(
    new Set(matches.map((object) => object.object_key || object.label || object.display_name).filter(Boolean))
  );

  return {
    available: true,
    evidenceIds: observation.id ? [observation.id] : [],
    label: matches[0]?.display_name || matches[0]?.label || "Water object",
    objectKeys
  };
}

function isDrinkContextObject(value?: string | null): boolean {
  if (!value) {
    return false;
  }
  const normalized = value.trim().toLowerCase().replace(/[\s-]+/g, "_");
  if (DRINK_CONTEXT_OBJECTS.has(normalized)) {
    return true;
  }
  return (
    normalized.includes("bottle") ||
    normalized.includes("cup") ||
    normalized.includes("glass") ||
    normalized.includes("water")
  );
}

function ActionEventRow({ event }: { event: ActionEvent }) {
  const metadata = event.metadata ?? {};
  const uncertainty = readMetadataText(metadata, "uncertainty") || readMetadataText(metadata, "fallback_reason");

  return (
    <article className="action-event-row">
      <div className="row-heading">
        <strong>{safeActionTitle(event)}</strong>
        <StatusPill label={sentenceCase(event.confidence)} tone={confidenceTone(event.confidence)} />
      </div>
      <p>{actionEventCopy(event)}</p>
      <dl className="compact-meta compact-meta--two">
        <div>
          <dt>Event ID</dt>
          <dd>{event.id}</dd>
        </div>
        <div>
          <dt>Score</dt>
          <dd>{typeof event.score === "number" ? event.score.toFixed(2) : "Unknown"}</dd>
        </div>
        <div>
          <dt>Node</dt>
          <dd>{event.source_node_id || "Unknown"}</dd>
        </div>
        <div>
          <dt>Occurred</dt>
          <dd>{formatDateTime(event.occurred_at)}</dd>
        </div>
      </dl>
      <EvidenceRefs ids={event.evidence_ids} label={`Evidence for ${event.id}`} />
      {uncertainty ? (
        <div className="action-uncertainty">
          <strong>Uncertainty</strong>
          <p>{uncertainty}</p>
        </div>
      ) : null}
    </article>
  );
}

function RuntimeStatusCard({
  body,
  label,
  title,
  tone
}: {
  body: string;
  label: string;
  title: string;
  tone: StatusTone;
}) {
  return (
    <div className="action-runtime-card">
      <div className="row-heading">
        <strong>{title}</strong>
        <StatusPill label={label} tone={tone} />
      </div>
      <p>{body}</p>
    </div>
  );
}

function successMessage(response: ActionTelemetryEvaluateResponse, title: string): ActionMessage {
  const event = response.event ?? response.action_event ?? null;
  return {
    tone: "success",
    title,
    body:
      response.message ||
      (event
        ? `${sentenceCase(event.type)} saved with ${sentenceCase(event.confidence)} confidence.`
        : "The backend accepted the compact telemetry.")
  };
}

function safeActionTitle(event: ActionEvent): string {
  if (isFallActionEvent(event)) {
    return "Possible fall candidate";
  }
  if (event.type === "drink_candidate") {
    return "Possible drink-action candidate";
  }
  return "Action review inconclusive";
}

function actionEventCopy(event: ActionEvent): string {
  if (event.type === "drink_candidate") {
    return "This may indicate a drink action. Bottle, cup, or water visibility is context only and is not confirmed hydration intake.";
  }
  if (isFallActionEvent(event)) {
    return "This notification has been escalated to the caregiver for a possible fall.";
  }
  return "The available signal was not enough to classify an action. Human review is appropriate.";
}

function isFallActionEvent(event: ActionEvent): boolean {
  return event.type === "fall_candidate" || event.type === "fall_escalated";
}

function readMetadataText(metadata: Record<string, unknown>, key: string): string {
  const value = metadata[key];
  if (typeof value === "string") {
    return value;
  }
  if (Array.isArray(value)) {
    return value.filter((item) => typeof item === "string").join("; ");
  }
  return "";
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

function mediaPipeStatusLabel(state: MediaPipeRuntimeState): string {
  if (state === "ready") {
    return "Ready";
  }
  if (state === "degraded") {
    return "Throttled";
  }
  if (state === "loading") {
    return "Loading";
  }
  if (state === "asset_load_failure") {
    return "Asset failed";
  }
  if (state === "camera_permission_denied") {
    return "Permission needed";
  }
  if (state === "stale_no_pose") {
    return "No pose";
  }
  if (state === "error") {
    return "Error";
  }
  if (state === "unavailable") {
    return "Unavailable";
  }
  return "Idle";
}

function mediaPipeStatusCopy(
  state: MediaPipeRuntimeState,
  metrics: ReturnType<typeof useBrowserActionRuntime>["metrics"]
): string {
  if (state === "ready") {
    return "Pose inference is running locally after Action Node start; drink submission still needs hand landmarks and object context.";
  }
  if (state === "degraded") {
    return "Action inference is performance-throttled to keep the browser responsive. Drinking can still log when hand landmarks, live object context, and the sip sequence are present.";
  }
  if (state === "loading") {
    return "Loading MediaPipe model and wasm assets after camera activation.";
  }
  if (state === "camera_permission_denied") {
    return "Allow camera access in the browser to use local action inference.";
  }
  if (state === "asset_load_failure") {
    return "MediaPipe model or wasm assets did not load. Use a reachable local/public asset URL before physical smoke.";
  }
  if (state === "stale_no_pose") {
    return metrics.framesAnalyzed
      ? "The camera is on, but no fresh human pose is visible. Reposition the camera or step into view."
      : "Waiting for the first pose frame.";
  }
  if (state === "error") {
    return "MediaPipe hit a runtime error. Stop and restart the local Action Node before using fallback controls.";
  }
  if (state === "unavailable") {
    return "MediaPipe could not initialize. Use fallback only for unavailable-state testing.";
  }
  return "Idle until the caregiver starts the browser Action Node.";
}

function mediaPipeTone(state: MediaPipeRuntimeState): StatusTone {
  if (state === "ready") {
    return "good";
  }
  if (state === "loading" || state === "degraded" || state === "stale_no_pose") {
    return "info";
  }
  if (
    state === "unavailable" ||
    state === "error" ||
    state === "asset_load_failure" ||
    state === "camera_permission_denied"
  ) {
    return "bad";
  }
  return "quiet";
}

function handStatusLabel(metrics: ReturnType<typeof useBrowserActionRuntime>["metrics"]): string {
  if (metrics.handSignalState === "ready") {
    return "Ready";
  }
  if (metrics.handSignalState === "loading") {
    return "Looking";
  }
  if (metrics.handSignalState === "error") {
    return "Error";
  }
  if (metrics.handSignalState === "unavailable") {
    return "Unavailable";
  }
  return "Idle";
}

function handStatusCopy(metrics: ReturnType<typeof useBrowserActionRuntime>["metrics"]): string {
  if (metrics.handSignalState === "ready") {
    return "MediaPipe hand landmarks are fresh enough for the hydration FSM.";
  }
  if (metrics.handSignalState === "loading") {
    return "Hand runtime loaded, but no fresh hand landmarks are visible yet.";
  }
  if (metrics.handSignalState === "error") {
    return "Hand landmark detection failed. Pose-only face proximity remains inconclusive.";
  }
  if (metrics.handSignalState === "unavailable") {
    return "Hand landmark runtime is unavailable, so drink submission is disabled instead of using pose-only wrist proximity.";
  }
  return "Idle until the Action Node starts.";
}

function handStatusTone(metrics: ReturnType<typeof useBrowserActionRuntime>["metrics"]): StatusTone {
  if (metrics.handSignalState === "ready") {
    return "good";
  }
  if (metrics.handSignalState === "loading") {
    return "info";
  }
  if (metrics.handSignalState === "error" || metrics.handSignalState === "unavailable") {
    return "bad";
  }
  return "quiet";
}

function hydrationStageLabel(stage: ReturnType<typeof useBrowserActionRuntime>["metrics"]["hydrationFsmStage"]): string {
  if (stage === "waiting_context") {
    return "Needs context";
  }
  if (stage === "waiting_pose") {
    return "Needs pose";
  }
  if (stage === "waiting_hand") {
    return "Needs hand";
  }
  if (stage === "tracking_approach") {
    return "Approach";
  }
  if (stage === "mouth_dwell") {
    return "Mouth dwell";
  }
  if (stage === "exit_cooldown") {
    return "Cooldown";
  }
  return "Ready";
}

function drinkRuntimeCanSubmit(
  state: MediaPipeRuntimeState,
  metrics: ReturnType<typeof useBrowserActionRuntime>["metrics"]
): boolean {
  return (state === "ready" || state === "degraded") && metrics.handRuntimeAvailable;
}

function drinkSubmissionDisabledReason(
  cupOrBottleContext: boolean,
  state: MediaPipeRuntimeState,
  metrics: ReturnType<typeof useBrowserActionRuntime>["metrics"]
): string {
  if (!cupOrBottleContext) {
    return "Waiting for live Afferens cup, bottle, or water context. Visibility is only context; the drink event still requires hand-to-mouth motion.";
  }
  if (!drinkRuntimeCanSubmit(state, metrics)) {
    return metrics.hydrationDisabledReason || "Hand landmark runtime must be ready; pose-only wrist-near-mouth is inconclusive.";
  }
  if (!metrics.drinkCandidateReady) {
    return metrics.hydrationDisabledReason || "Waiting for hand/object context, hand-to-mouth approach, brief mouth dwell, and exit.";
  }
  return "";
}

function runtimeModeLabel(mode: ReturnType<typeof useBrowserActionRuntime>["metrics"]["runtimeMode"]): string {
  if (mode === "main_thread_throttled") {
    return "Main thread, throttled";
  }
  return "Idle";
}

function assetStatusLabel(
  status: ReturnType<typeof useBrowserActionRuntime>["metrics"]["assetStatus"]
): string {
  if (status === "ok") {
    return "Reachable";
  }
  if (status === "cors_unverified") {
    return "Loader will verify";
  }
  if (status === "failed") {
    return "Failed";
  }
  if (status === "not_run") {
    return "Not required";
  }
  return "Not checked";
}

function fallRuntimeReady(status?: ActionRuntimeStatusResponse): boolean {
  return Boolean(status?.fall?.available && status.fall.enabled !== false);
}

function fallStatusLabel(status: Loadable<ActionRuntimeStatusResponse>): string {
  const fall = status.data?.fall;
  if (status.loading && !status.data) {
    return "Checking";
  }
  if (status.error) {
    return "Unavailable";
  }
  if (!fall?.enabled) {
    return "Disabled";
  }
  if (!fall.model_path_configured) {
    return "Model missing";
  }
  return fall.available ? "Ready" : "Unavailable";
}

function fallStatusCopy(status: Loadable<ActionRuntimeStatusResponse>): string {
  const fall = status.data?.fall;
  if (status.loading && !status.data) {
    return "Checking backend runtime registration before fall analysis is enabled.";
  }
  if (status.error) {
    return "Runtime status endpoint is unavailable, so fall frame analysis stays disabled.";
  }
  if (!fall) {
    return "Backend did not return fall runtime details.";
  }
  return fall.message || "Backend fall runtime status is available.";
}

function fallStatusTone(status: Loadable<ActionRuntimeStatusResponse>): StatusTone {
  if (fallRuntimeReady(status.data)) {
    return "good";
  }
  if (status.loading) {
    return "info";
  }
  if (status.error || status.data?.fall?.enabled) {
    return "warn";
  }
  return "quiet";
}

function cameraLabel(state: CameraState): string {
  if (state === "on") {
    return "Local preview on";
  }
  if (state === "starting") {
    return "Starting";
  }
  if (state === "unsupported") {
    return "Unsupported";
  }
  if (state === "blocked") {
    return "Permission needed";
  }
  return "Preview off";
}

function cameraTone(state: CameraState): StatusTone {
  if (state === "on") {
    return "good";
  }
  if (state === "blocked") {
    return "bad";
  }
  if (state === "starting") {
    return "info";
  }
  return "quiet";
}

function optionalValue(value: string): string | undefined {
  return value.trim() || undefined;
}

function isUnavailable(error: unknown): boolean {
  const status = error instanceof Error && "status" in error ? Number(error.status) : undefined;
  return isUnavailableEndpoint(status);
}

function errorMessage(error: unknown, fallback: string): ActionMessage {
  if (isUnavailable(error)) {
    return {
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
        ? "Action-event endpoint unavailable."
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
