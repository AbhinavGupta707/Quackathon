import { formatDateTime, sentenceCase } from "@/lib/format";
import type { Loadable, TasksResponse } from "@/lib/types";
import { EvidenceRefs } from "./EvidenceRefs";
import { Panel } from "./Panel";
import { StateBlock } from "./StateBlock";
import { StatusPill, type StatusTone } from "./StatusPill";

type ActiveTaskConsoleProps = {
  tasks: Loadable<TasksResponse>;
};

export function ActiveTaskConsole({ tasks }: ActiveTaskConsoleProps) {
  const allTasks = tasks.data?.tasks ?? [];
  const activeTasks = allTasks.filter((task) => !["verified_resolved", "dismissed"].includes(task.state));
  const recentlyClosedTasks = allTasks.filter((task) => ["verified_resolved", "dismissed"].includes(task.state)).slice(0, 3);

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
          {activeTasks.map((task) => (
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
                <button className="button button--secondary" type="button" disabled title="Backend verification endpoint is not wired in this UI yet.">
                  Verify with live perception
                </button>
                <button className="button button--secondary" type="button" disabled title="Backend resolution endpoint is not wired in this UI yet.">
                  Mark resolved
                </button>
              </div>
            </article>
          ))}
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
