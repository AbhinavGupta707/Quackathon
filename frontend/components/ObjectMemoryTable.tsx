import { formatDateTime, formatPercent, objectStatusLabel } from "@/lib/format";
import type { Loadable, ObjectsResponse } from "@/lib/types";
import { EvidenceRefs } from "./EvidenceRefs";
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
                <th scope="col">Room</th>
                <th scope="col">Location detail</th>
                <th scope="col">Confidence</th>
                <th scope="col">Evidence</th>
              </tr>
            </thead>
            <tbody>
              {objects.data.objects.map((object) => (
                <tr key={object.object_key}>
                  <td>
                    <strong>{object.display_name}</strong>
                    <span>{object.object_key}</span>
                  </td>
                  <td>
                    <StatusPill label={objectStatusLabel(object.status)} tone={object.status === "visible_now" ? "good" : "quiet"} />
                  </td>
                  <td>{formatDateTime(object.last_seen_at)}</td>
                  <td>{object.last_seen_room || "Unknown"}</td>
                  <td>{object.last_seen_relative_location || "Unknown"}</td>
                  <td>{formatPercent(object.last_confidence)}</td>
                  <td>
                    <EvidenceRefs ids={[object.last_seen_observation_id]} label={`Evidence for ${object.display_name}`} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}
