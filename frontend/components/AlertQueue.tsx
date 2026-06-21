import { formatDateTime, sentenceCase } from "@/lib/format";
import type { AlertsResponse, Loadable } from "@/lib/types";
import { EvidenceRefs } from "./EvidenceRefs";
import { Panel } from "./Panel";
import { StateBlock } from "./StateBlock";
import { StatusPill, type StatusTone } from "./StatusPill";

type AlertQueueProps = {
  alerts: Loadable<AlertsResponse>;
};

export function AlertQueue({ alerts }: AlertQueueProps) {
  const openAlerts = alerts.data?.alerts.filter((alert) => alert.status === "open") ?? [];

  return (
    <Panel title="Caregiver And Escalation" eyebrow="Conservative Safety Queue">
      {alerts.loading ? (
        <StateBlock tone="loading" title="Loading alerts" body="Checking caregiver-facing safety alerts." />
      ) : alerts.error ? (
        <StateBlock tone="error" title="Alert endpoint unavailable" body={alerts.error} />
      ) : openAlerts.length === 0 ? (
        <StateBlock
          title="No open alerts"
          body="Possible risks will appear only when a live observation creates alert evidence. Human verification remains required."
        />
      ) : (
        <div className="alert-list">
          {openAlerts.map((alert) => (
            <article className="alert-row" key={alert.id}>
              <div className="row-heading">
                <h3>{alert.title}</h3>
                <StatusPill label={sentenceCase(alert.severity)} tone={toneForSeverity(alert.severity)} />
              </div>
              <p>{alert.body}</p>
              {alert.recommended_action ? <p className="recommended">{alert.recommended_action}</p> : null}
              <dl>
                <div>
                  <dt>Created</dt>
                  <dd>{formatDateTime(alert.created_at)}</dd>
                </div>
                <div>
                  <dt>Hazard</dt>
                  <dd>{sentenceCase(alert.hazard_type)}</dd>
                </div>
                <div>
                  <dt>Evidence</dt>
                  <dd>
                    <EvidenceRefs ids={alert.evidence_observation_ids} label={`Evidence for ${alert.title}`} />
                  </dd>
                </div>
              </dl>
              <div className="task-actions" aria-label={`Alert controls for ${alert.title}`}>
                <button className="button button--secondary" type="button" disabled title="Alert acknowledgement is reserved for Checkpoint 3 integration.">
                  Acknowledge
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </Panel>
  );
}

function toneForSeverity(severity: string): StatusTone {
  if (severity === "high") {
    return "bad";
  }
  if (severity === "medium") {
    return "warn";
  }
  return "info";
}
