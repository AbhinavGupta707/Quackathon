import { formatDateTime, formatPercent, sentenceCase } from "@/lib/format";
import type { Loadable, ObjectsResponse } from "@/lib/types";
import { Panel } from "./Panel";
import { StateBlock } from "./StateBlock";
import { StatusPill } from "./StatusPill";

type ObjectMemoryTableProps = {
  objects: Loadable<ObjectsResponse>;
};

export function ObjectMemoryTable({ objects }: ObjectMemoryTableProps) {
  return (
    <Panel title="Object Memory" eyebrow="Last Seen From Live Evidence">
      {objects.loading ? (
        <StateBlock tone="loading" title="Loading object memory" body="Reading live-backed last-seen object records." />
      ) : objects.error ? (
        <StateBlock tone="error" title="Object memory unavailable" body={objects.error} />
      ) : !objects.data?.objects.length ? (
        <StateBlock
          title="No objects remembered yet"
          body="Run a live perception sync after an Afferens Node is active. Fixture or replayed objects are not displayed here."
        />
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Object</th>
                <th scope="col">Status</th>
                <th scope="col">Last seen</th>
                <th scope="col">Location</th>
                <th scope="col">Evidence</th>
              </tr>
            </thead>
            <tbody>
              {objects.data.objects.map((object) => (
                <tr key={object.object_key}>
                  <td>
                    <strong>{object.display_name}</strong>
                    <span>{formatPercent(object.last_confidence)}</span>
                  </td>
                  <td>
                    <StatusPill label={sentenceCase(object.status)} tone={object.status === "visible_now" ? "good" : "quiet"} />
                  </td>
                  <td>{formatDateTime(object.last_seen_at)}</td>
                  <td>{object.last_seen_relative_location || object.last_seen_room || "Unknown"}</td>
                  <td>{object.last_seen_observation_id || "Not linked"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}
