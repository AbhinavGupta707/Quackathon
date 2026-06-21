import { formatDateTime, formatPercent, sentenceCase } from "@/lib/format";
import type { LatestObservationResponse, Loadable } from "@/lib/types";
import { Panel } from "./Panel";
import { StateBlock } from "./StateBlock";
import { StatusPill } from "./StatusPill";

type ObservationPanelProps = {
  latestObservation: Loadable<LatestObservationResponse>;
  onSync: () => void;
  syncPending: boolean;
  syncError?: string;
};

export function ObservationPanel({ latestObservation, onSync, syncPending, syncError }: ObservationPanelProps) {
  const observation = latestObservation.data?.observation;

  return (
    <Panel
      title="Latest Live Observation"
      eyebrow="Afferens Evidence"
      action={
        <button className="button button--primary" type="button" onClick={onSync} disabled={syncPending}>
          {syncPending ? "Syncing" : "Sync Live Perception"}
        </button>
      }
    >
      {latestObservation.loading ? (
        <StateBlock tone="loading" title="Loading observation" body="Checking the backend for the latest normalized live observation." />
      ) : latestObservation.error ? (
        <StateBlock tone="error" title="Observation endpoint unavailable" body={latestObservation.error} />
      ) : !observation ? (
        <StateBlock
          title="No live observation yet"
          body="Start an Afferens Node, then sync perception. The app will not show cached or replayed perception as current evidence."
        />
      ) : (
        <div className="observation">
          <div className="observation__summary">
            <StatusPill label={observation.source || "afferens"} tone="info" />
            <h3>{observation.scene_summary || "Live scene summary unavailable"}</h3>
            <p>
              {formatDateTime(observation.timestamp_utc)} from {observation.source_node_id || "unknown node"}.
              Human presence: {sentenceCase(observation.human_presence || "unknown")}.
            </p>
          </div>

          <dl className="metric-grid">
            <div>
              <dt>Observation ID</dt>
              <dd>{observation.id}</dd>
            </div>
            <div>
              <dt>Raw event</dt>
              <dd>{observation.raw_event_id}</dd>
            </div>
            <div>
              <dt>Classification</dt>
              <dd>{observation.classification || "Unknown"}</dd>
            </div>
            <div>
              <dt>Confidence</dt>
              <dd>{formatPercent(observation.confidence)}</dd>
            </div>
          </dl>

          <div className="object-chips" aria-label="Objects visible in latest observation">
            {observation.objects.length > 0 ? (
              observation.objects.map((object) => (
                <span className="object-chip" key={`${object.object_key}-${object.label}`}>
                  {object.display_name}
                  <small>{formatPercent(object.confidence)}</small>
                </span>
              ))
            ) : (
              <p className="muted">No objects were normalized from the latest live observation.</p>
            )}
          </div>
        </div>
      )}

      {syncError ? <StateBlock tone="error" title="Live sync failed" body={syncError} /> : null}
    </Panel>
  );
}
