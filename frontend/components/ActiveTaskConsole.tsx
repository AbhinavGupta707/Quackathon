import { formatDateTime, sentenceCase } from "@/lib/format";
import type { Loadable, TasksResponse } from "@/lib/types";
import { Panel } from "./Panel";
import { StateBlock } from "./StateBlock";
import { StatusPill, type StatusTone } from "./StatusPill";

type ActiveTaskConsoleProps = {
  tasks: Loadable<TasksResponse>;
};

export function ActiveTaskConsole({ tasks }: ActiveTaskConsoleProps) {
  const activeTasks =
    tasks.data?.tasks.filter((task) => !["verified_resolved", "dismissed"].includes(task.state)) ?? [];

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
              <dl>
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
                  <dd>{task.evidence_observation_ids.join(", ") || "Not linked"}</dd>
                </div>
              </dl>
            </article>
          ))}
        </div>
      )}
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
