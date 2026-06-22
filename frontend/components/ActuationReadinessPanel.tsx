"use client";

import { useMemo, useState } from "react";
import { ApiError, captureFrameForTask, triggerAssistiveAlarm } from "@/lib/api";
import type {
  ActuationResponse,
  AfferensStatus,
  Alert,
  AlertsResponse,
  Loadable,
  Task,
  TasksResponse
} from "@/lib/types";
import { Panel } from "./Panel";
import { StateBlock } from "./StateBlock";
import { StatusPill } from "./StatusPill";

type ActuationReadinessPanelProps = {
  afferens: Loadable<AfferensStatus>;
  alerts: Loadable<AlertsResponse>;
  tasks: Loadable<TasksResponse>;
};

type ActionState = {
  loading?: "alarm" | "capture";
  error?: string;
  result?: ActuationResponse;
};

export function ActuationReadinessPanel({ afferens, alerts, tasks }: ActuationReadinessPanelProps) {
  const [actionState, setActionState] = useState<ActionState>({});
  const openAlerts = useMemo(
    () => (alerts.data?.alerts ?? []).filter((alert) => alert.status === "open"),
    [alerts.data?.alerts]
  );
  const activeTasks = useMemo(
    () => (tasks.data?.tasks ?? []).filter((task) => !["verified_resolved", "dismissed"].includes(task.state)),
    [tasks.data?.tasks]
  );
  const primaryAlert = openAlerts[0];
  const primaryTask = activeTasks[0] ?? taskForAlert(primaryAlert, activeTasks);
  const hasEvidence = Boolean(primaryAlert?.evidence_observation_ids.length || primaryTask?.evidence_observation_ids.length);
  const backendPending = actionState.loading;

  async function runAlarm() {
    setActionState({ loading: "alarm" });
    try {
      const result = await triggerAssistiveAlarm({
        reason: primaryAlert?.hazard_type || primaryTask?.type || "caregiver_review",
        severity: primaryAlert?.severity || "medium",
        taskId: primaryAlert?.task_id || primaryTask?.id
      });
      setActionState({ result });
    } catch (error) {
      setActionState({ error: messageForActuationError(error) });
    }
  }

  async function runCaptureFrame() {
    setActionState({ loading: "capture" });
    try {
      const result = await captureFrameForTask({
        taskId: primaryAlert?.task_id || primaryTask?.id,
        targetNodeId: afferens.data?.source_node_id
      });
      setActionState({ result });
    } catch (error) {
      setActionState({ error: messageForActuationError(error) });
    }
  }

  return (
    <Panel title="Action Readiness" eyebrow="Assistive Controls">
      <div className="action-readiness-grid">
        <div className="readiness-card">
          <div className="row-heading">
            <h3>Assistive alarm</h3>
            <StatusPill label="Reserved" tone="quiet" />
          </div>
          <p>Use for an evidence-linked alert when the backend exposes actuation.</p>
          <button
            className="button button--secondary"
            disabled={Boolean(backendPending) || !hasEvidence}
            onClick={() => void runAlarm()}
            type="button"
          >
            {backendPending === "alarm" ? "Trying alarm" : "Try alarm"}
          </button>
        </div>

        <div className="readiness-card">
          <div className="row-heading">
            <h3>Capture frame</h3>
            <StatusPill label="Reserved" tone="quiet" />
          </div>
          <p>Request a fresh frame for review without replacing normal live sync.</p>
          <button
            className="button button--secondary"
            disabled={Boolean(backendPending) || !afferens.data?.source_node_id}
            onClick={() => void runCaptureFrame()}
            type="button"
          >
            {backendPending === "capture" ? "Trying capture" : "Try capture"}
          </button>
        </div>
      </div>

      {!hasEvidence ? (
        <StateBlock
          title="No linked evidence yet"
          body="Actions stay disabled until a task or alert cites live observation evidence."
        />
      ) : null}

      {!afferens.data?.source_node_id ? (
        <StateBlock
          title="No target node yet"
          body="Capture remains disabled until Afferens reports a live source node."
        />
      ) : null}

      {actionState.error ? (
        <StateBlock tone="error" title="Actuation unavailable" body={actionState.error} />
      ) : actionState.result ? (
        <StateBlock
          tone={actionState.result.ok ? "success" : "error"}
          title={actionState.result.attempt.state}
          body={actionState.result.attempt.message}
        />
      ) : (
        <StateBlock
          title="Backend endpoint not required"
          body="The existing sync, query, verification, resolve, and acknowledgement flows continue without actuation."
        />
      )}
    </Panel>
  );
}

function taskForAlert(alert: Alert | undefined, tasks: Task[]): Task | undefined {
  if (!alert?.task_id) {
    return undefined;
  }
  return tasks.find((task) => task.id === alert.task_id);
}

function messageForActuationError(error: unknown): string {
  if (error instanceof ApiError && error.status === 404) {
    return "This backend does not expose actuation endpoints yet.";
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Actuation endpoint unavailable.";
}
