import type { AfferensStatus, HealthResponse, Loadable } from "@/lib/types";
import { Panel } from "./Panel";
import { StatusPill } from "./StatusPill";

type NodeSetupChecklistProps = {
  health: Loadable<HealthResponse>;
  afferens: Loadable<AfferensStatus>;
};

const nodeOptions = [
  {
    name: "Laptop webcam",
    detail: "Use the current computer as the Afferens Vision Node when camera permission is available."
  },
  {
    name: "Phone camera",
    detail: "Open the node setup flow on a phone for a movable view of the home zone."
  },
  {
    name: "USB webcam",
    detail: "Attach an external webcam when the scene needs a stable or wider field of view."
  }
];

export function NodeSetupChecklist({ health, afferens }: NodeSetupChecklistProps) {
  const status = afferens.data;

  const steps = [
    {
      label: "Backend registration",
      detail: "Confirm /api/health is reachable before checking downstream integrations.",
      done: Boolean(health.data?.ok),
      blocked: Boolean(health.error)
    },
    {
      label: "Server-side Afferens key",
      detail: "The frontend never asks for or displays the API key.",
      done: Boolean(status?.configured),
      blocked: status?.state === "missing_key"
    },
    {
      label: "Account and key status",
      detail: "Invalid or inactive keys should be fixed before camera or parsing work.",
      done: status?.state === "live" || status?.state === "no_live_events",
      blocked: status?.state === "invalid_key" || status?.state === "inactive_key"
    },
    {
      label: "Node setup",
      detail: "Use an official Afferens Node option: laptop webcam, phone camera, or USB webcam.",
      done: status?.state === "live",
      blocked: false
    },
    {
      label: "Live perception event",
      detail: "The product remains in no-live-node mode until /api/afferens/latest can see a live event.",
      done: status?.state === "live",
      blocked: status?.state === "error"
    }
  ];

  return (
    <Panel
      title="Afferens Node Setup"
      eyebrow="Activation Order"
      action={
        <a className="button button--secondary" href="https://afferens.com/node" rel="noreferrer" target="_blank">
          Open Node Setup
        </a>
      }
    >
      <ol className="checklist">
        {steps.map((step) => (
          <li className="checklist__item" key={step.label}>
            <StatusPill label={step.done ? "Ready" : step.blocked ? "Blocked" : "Pending"} tone={step.done ? "good" : step.blocked ? "bad" : "warn"} />
            <div>
              <strong>{step.label}</strong>
              <p>{step.detail}</p>
            </div>
          </li>
        ))}
      </ol>

      <div className="node-options" aria-label="Supported Afferens Node camera options">
        {nodeOptions.map((option) => (
          <article className="node-option" key={option.name}>
            <h3>{option.name}</h3>
            <p>{option.detail}</p>
          </article>
        ))}
      </div>
    </Panel>
  );
}
