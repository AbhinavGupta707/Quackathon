import { formatDateTime, formatPercent, sentenceCase } from "@/lib/format";
import type { LatestObservationResponse, Loadable, SyncResponse } from "@/lib/types";
import { EvidenceRefs } from "./EvidenceRefs";
import { Panel } from "./Panel";
import { StateBlock } from "./StateBlock";
import { StatusPill } from "./StatusPill";

type ObservationPanelProps = {
  latestObservation: Loadable<LatestObservationResponse>;
  onSync: () => void;
  syncPending: boolean;
  syncError?: string;
  syncResult?: SyncResponse | null;
};

export function ObservationPanel({
  latestObservation,
  onSync,
  syncPending,
  syncError,
  syncResult
}: ObservationPanelProps) {
  const observation = latestObservation.data?.observation;
  const observationObjects = observation?.objects ?? [];
  const riskSignals = observation?.risk_signals ?? [];

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
        <StateBlock
          tone="loading"
          title="Loading observation"
          body="Checking the backend for the latest normalized live observation."
        />
      ) : latestObservation.error ? (
        <StateBlock tone="error" title="Observation endpoint unavailable" body={latestObservation.error} />
      ) : !observation ? (
        <StateBlock
          title="No live observation yet"
          body="Start an Afferens Node, then sync perception. The app will not show cached or replayed perception as current evidence."
        />
      ) : (
        <div className="observation" id="latest-observation">
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
              <dd>
                <EvidenceRefs ids={[observation.id]} label="Latest observation ID" />
              </dd>
            </div>
            <div>
              <dt>Raw event</dt>
              <dd>{observation.raw_event_id}</dd>
            </div>
            <div>
              <dt>Source node</dt>
              <dd>{observation.source_node_id || "Unknown"}</dd>
            </div>
            <div>
              <dt>Modality</dt>
              <dd>{observation.modality || "Unknown"}</dd>
            </div>
            <div>
              <dt>Room</dt>
              <dd>{observation.room_id || "Unknown"}</dd>
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

          <div className="evidence-subpanel">
            <div className="row-heading">
              <h3>Detected objects</h3>
              <StatusPill
                label={`${observationObjects.length} normalized`}
                tone={observationObjects.length ? "good" : "quiet"}
              />
            </div>
            {observationObjects.length > 0 ? (
              <div className="detected-object-grid">
                {observationObjects.map((detectedObject) => (
                  <article className="detected-object" key={`${detectedObject.object_key}-${detectedObject.label}`}>
                    <div className="row-heading">
                      <strong>{detectedObject.display_name}</strong>
                      <span>{formatPercent(detectedObject.confidence)}</span>
                    </div>
                    <p>{detectedObject.relative_location || "Location detail unavailable"}</p>
                    <dl>
                      <div>
                        <dt>Object key</dt>
                        <dd>{detectedObject.object_key}</dd>
                      </div>
                      <div>
                        <dt>Source</dt>
                        <dd>{detectedObject.source || "Unknown"}</dd>
                      </div>
                    </dl>
                  </article>
                ))}
              </div>
            ) : (
              <p className="muted">No objects were normalized from the latest live observation.</p>
            )}
          </div>

          <div className="evidence-subpanel">
            <div className="row-heading">
              <h3>Risk signals</h3>
              <StatusPill label={`${riskSignals.length} reported`} tone={riskSignals.length ? "warn" : "quiet"} />
            </div>
            {riskSignals.length > 0 ? (
              <ul className="plain-list">
                {riskSignals.map((signal, index) => (
                  <li key={index}>{typeof signal === "string" ? signal : JSON.stringify(signal)}</li>
                ))}
              </ul>
            ) : (
              <p className="muted">No risk signals were returned for this observation.</p>
            )}
          </div>
        </div>
      )}

      {syncResult ? (
        <StateBlock
          tone={syncResult.ok ? "success" : "error"}
          title={syncResult.ok ? "Live sync completed" : "Live sync returned a problem"}
          body={`Created ${syncResult.observations?.length ?? 0} observation(s), updated ${
            syncResult.objects_updated?.length ?? 0
          } object memory record(s), opened ${syncResult.tasks_created?.length ?? 0} task(s), and created ${
            syncResult.alerts_created?.length ?? 0
          } alert(s).`}
        />
      ) : syncPending ? (
        <StateBlock
          tone="loading"
          title="Syncing live perception"
          body="The backend is fetching current Afferens Vision data, normalizing observations, and updating live-backed memory."
        />
      ) : null}

      {syncError ? <StateBlock tone="error" title="Live sync failed" body={syncError} /> : null}
    </Panel>
  );
}
