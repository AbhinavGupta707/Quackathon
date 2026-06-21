import { API_BASE_URL } from "@/lib/api";
import { formatDateTime, sentenceCase } from "@/lib/format";
import type { AfferensStatus, HealthResponse, Loadable } from "@/lib/types";
import { Panel } from "./Panel";
import { StateBlock } from "./StateBlock";
import { StatusPill, type StatusTone } from "./StatusPill";

type LiveStatusPanelProps = {
  health: Loadable<HealthResponse>;
  afferens: Loadable<AfferensStatus>;
  onRefresh: () => void;
};

export function LiveStatusPanel({ health, afferens, onRefresh }: LiveStatusPanelProps) {
  const backendTone = health.data?.ok ? "good" : health.error ? "bad" : "warn";
  const afferensTone = afferens.data ? afferensToneFor(afferens.data.state) : afferens.error ? "bad" : "warn";

  return (
    <Panel
      title="Live System Status"
      eyebrow="Live-Only Runtime"
      action={
        <button className="button button--secondary" type="button" onClick={onRefresh}>
          Refresh
        </button>
      }
    >
      <div className="status-grid" aria-live="polite">
        <div className="status-card">
          <div className="status-card__topline">
            <span>Backend</span>
            <StatusPill label={health.loading ? "Checking" : health.data?.ok ? "Reachable" : "Unavailable"} tone={backendTone} />
          </div>
          <p>{health.error || health.data?.services?.database?.message || "Waiting for /api/health."}</p>
          <dl>
            <div>
              <dt>API base</dt>
              <dd>{API_BASE_URL}</dd>
            </div>
            <div>
              <dt>Environment</dt>
              <dd>{health.data?.environment || "Unknown"}</dd>
            </div>
          </dl>
        </div>

        <div className="status-card">
          <div className="status-card__topline">
            <span>Afferens</span>
            <StatusPill
              label={afferens.loading ? "Checking" : afferens.data ? sentenceCase(afferens.data.state) : "Unavailable"}
              tone={afferensTone}
            />
          </div>
          <p>
            {afferens.error ||
              afferens.data?.message ||
              "Waiting for /api/afferens/status. Memory and tasks remain unavailable until live evidence is present."}
          </p>
          <dl>
            <div>
              <dt>Configured</dt>
              <dd>{afferens.data ? (afferens.data.configured ? "Server-side key present" : "Missing server config") : "Unknown"}</dd>
            </div>
            <div>
              <dt>Last event</dt>
              <dd>{afferens.data?.latest_event_id || "No live event reported"}</dd>
            </div>
            <div>
              <dt>Checked</dt>
              <dd>{formatDateTime(afferens.data?.latest_timestamp_utc)}</dd>
            </div>
          </dl>
        </div>
      </div>

      {health.error || afferens.error ? (
        <StateBlock
          tone="error"
          title="Connectivity needs checking"
          body="The shell can load, but at least one live backend endpoint is unavailable. Start the backend and confirm the configured API base before debugging camera or runtime logic."
        />
      ) : null}
    </Panel>
  );
}

function afferensToneFor(state: AfferensStatus["state"]): StatusTone {
  if (state === "live") {
    return "good";
  }
  if (state === "missing_key" || state === "invalid_key" || state === "inactive_key" || state === "error") {
    return "bad";
  }
  return "warn";
}
