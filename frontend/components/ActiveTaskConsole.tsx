"use client";

import { FormEvent, useState } from "react";
import { formatDateTime, sentenceCase } from "@/lib/format";
import type { Loadable, TaskResolveResponse, TasksResponse, TaskVerifyResponse } from "@/lib/types";
import { EvidenceRefs } from "./EvidenceRefs";
import { Panel } from "./Panel";
import { StateBlock } from "./StateBlock";
import { StatusPill, type StatusTone } from "./StatusPill";

type ActiveTaskConsoleProps = {
  tasks: Loadable<TasksResponse>;
  onResolve: (taskId: string, resolutionNote: string) => Promise<TaskResolveResponse>;
  onVerify: (taskId: string) => Promise<TaskVerifyResponse>;
};

type TaskActionState = {
  error?: string;
  loading?: "resolve" | "verify";
  message?: string;
  result?: "human_resolved" | "verified" | "not_verified" | "inconclusive";
};

export function ActiveTaskConsole({ tasks, onResolve, onVerify }: ActiveTaskConsoleProps) {
  const allTasks = tasks.data?.tasks ?? [];
  const activeTasks = allTasks.filter((task) => !["verified_resolved", "dismissed"].includes(task.state));
  const recentlyClosedTasks = allTasks.filter((task) => ["verified_resolved", "dismissed"].includes(task.state)).slice(0, 3);
  const [actionStateByTask, setActionStateByTask] = useState<Record<string, TaskActionState>>({});
  const [resolutionFormTaskId, setResolutionFormTaskId] = useState<string | null>(null);
  const [resolutionNotes, setResolutionNotes] = useState<Record<string, string>>({});

  async function handleVerify(taskId: string) {
    setActionStateByTask((previous) => ({
      ...previous,
      [taskId]: { loading: "verify" }
    }));

    try {
      const result = await onVerify(taskId);
      setActionStateByTask((previous) => ({
        ...previous,
        [taskId]: {
          message: result.verification.message,
          result: result.verification.state
        }
      }));
    } catch (error) {
      setActionStateByTask((previous) => ({
        ...previous,
        [taskId]: {
          error: error instanceof Error ? error.message : "Live verification failed."
        }
      }));
    }
  }

  async function handleResolve(event: FormEvent<HTMLFormElement>, taskId: string) {
    event.preventDefault();

    const note = resolutionNotes[taskId]?.trim();
    if (!note) {
      setActionStateByTask((previous) => ({
        ...previous,
        [taskId]: { error: "Add a short note for the human-reported resolution." }
      }));
      return;
    }

    setActionStateByTask((previous) => ({
      ...previous,
      [taskId]: { loading: "resolve" }
    }));

    try {
      await onResolve(taskId, note);
      setResolutionFormTaskId(null);
      setResolutionNotes((previous) => ({ ...previous, [taskId]: "" }));
      setActionStateByTask((previous) => ({
        ...previous,
        [taskId]: {
          message: "Human-reported resolution recorded.",
          result: "human_resolved"
        }
      }));
    } catch (error) {
      setActionStateByTask((previous) => ({
        ...previous,
        [taskId]: {
          error: error instanceof Error ? error.message : "Human resolution could not be recorded."
        }
      }));
    }
  }

  return (
    <Panel title="Active Task Console" eyebrow="Resolution Loop">
      {tasks.loading ? (
        <StateBlock tone="loading" title="Loading tasks" body="Checking open object-recovery and safety tasks." />
      ) : tasks.error ? (
        <StateBlock tone="error" title="Task endpoint unavailable" body={tasks.error} />
      ) : activeTasks.length === 0 ? (
        <StateBlock
          title="No active tasks"
          body="Tasks will appear after live observations create object-recovery or safety workflows."
        />
      ) : (
        <div className="task-list">
          {activeTasks.map((task) => {
            const actionState = actionStateByTask[task.id] ?? {};
            const busy = Boolean(actionState.loading);
            const formId = `resolution-note-${task.id}`;
            const resolutionFormOpen = resolutionFormTaskId === task.id;

            return (
              <article className="task-row" key={task.id}>
                <div>
                  <div className="row-heading">
                    <h3>{task.title}</h3>
                    <StatusPill label={sentenceCase(task.state)} tone={toneForTask(task.state)} />
                  </div>
                  <p>{task.body}</p>
                  {task.recommended_action ? <p className="recommended">{task.recommended_action}</p> : null}
                </div>
                <dl className="task-meta">
                  <div>
                    <dt>Type</dt>
                    <dd>{sentenceCase(task.type)}</dd>
                  </div>
                  <div>
                    <dt>Updated</dt>
                    <dd>{formatDateTime(task.updated_at)}</dd>
                  </div>
                  <div>
                    <dt>Evidence</dt>
                    <dd>
                      <EvidenceRefs ids={task.evidence_observation_ids} label={`Evidence for ${task.title}`} />
                    </dd>
                  </div>
                </dl>
                <div className="task-actions" aria-label={`Task controls for ${task.title}`}>
                  <button
                    className="button button--secondary"
                    disabled={busy}
                    onClick={() => void handleVerify(task.id)}
                    type="button"
                  >
                    {actionState.loading === "verify" ? "Verifying" : "Verify with live perception"}
                  </button>
                  <button
                    aria-expanded={resolutionFormOpen}
                    className="button button--secondary"
                    disabled={busy}
                    onClick={() => setResolutionFormTaskId(resolutionFormOpen ? null : task.id)}
                    type="button"
                  >
                    Mark resolved
                  </button>
                </div>

                {resolutionFormOpen ? (
                  <form className="resolution-form" onSubmit={(event) => void handleResolve(event, task.id)}>
                    <label htmlFor={formId}>Resolution note</label>
                    <textarea
                      disabled={busy}
                      id={formId}
                      name="resolution_note"
                      onChange={(event) =>
                        setResolutionNotes((previous) => ({
                          ...previous,
                          [task.id]: event.target.value
                        }))
                      }
                      placeholder="Example: I found the item and put it away."
                      rows={3}
                      value={resolutionNotes[task.id] ?? ""}
                    />
                    <div className="task-actions">
                      <button className="button button--primary" disabled={busy} type="submit">
                        {actionState.loading === "resolve" ? "Recording" : "Record human resolution"}
                      </button>
                      <button
                        className="button button--secondary"
                        disabled={busy}
                        onClick={() => setResolutionFormTaskId(null)}
                        type="button"
                      >
                        Cancel
                      </button>
                    </div>
                    <p className="muted">This records an explicit user-reported resolution.</p>
                  </form>
                ) : null}

                {actionState.error ? (
                  <StateBlock tone="error" title="Task action failed" body={actionState.error} />
                ) : actionState.message ? (
                  <StateBlock
                    tone={actionState.result === "verified" || actionState.result === "human_resolved" ? "success" : "empty"}
                    title={titleForActionResult(actionState.result)}
                    body={actionState.message}
                  />
                ) : null}
              </article>
            );
          })}
        </div>
      )}

      {!tasks.loading && !tasks.error && recentlyClosedTasks.length > 0 ? (
        <div className="closed-task-strip" aria-label="Recently closed tasks">
          <h3>Recently closed</h3>
          {recentlyClosedTasks.map((task) => (
            <div className="closed-task" key={task.id}>
              <span>{task.title}</span>
              <StatusPill label={sentenceCase(task.state)} tone={toneForTask(task.state)} />
            </div>
          ))}
        </div>
      ) : null}
    </Panel>
  );
}

function titleForActionResult(result?: TaskActionState["result"]): string {
  if (result === "verified") {
    return "Live verification verified";
  }
  if (result === "not_verified") {
    return "Live verification not verified";
  }
  if (result === "inconclusive") {
    return "Live verification inconclusive";
  }
  return "Human resolution recorded";
}

function toneForTask(state: string): StatusTone {
  if (state === "verified_resolved") {
    return "good";
  }
  if (state === "escalated" || state === "failed_verification") {
    return "bad";
  }
  if (state === "verification_pending" || state === "waiting_for_human") {
    return "warn";
  }
  return "info";
}
