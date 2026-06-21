"use client";

import { useState } from "react";

type EvidenceRefsProps = {
  ids?: Array<string | null | undefined> | null;
  label?: string;
};

export function EvidenceRefs({ ids, label = "Observation evidence" }: EvidenceRefsProps) {
  const cleanIds = (ids ?? []).filter((id): id is string => Boolean(id));
  const [copiedId, setCopiedId] = useState<string | null>(null);

  if (cleanIds.length === 0) {
    return <span className="muted">No evidence IDs returned</span>;
  }

  async function copyEvidence(id: string) {
    try {
      await navigator.clipboard.writeText(id);
      setCopiedId(id);
      window.setTimeout(() => setCopiedId((current) => (current === id ? null : current)), 1600);
    } catch {
      setCopiedId(null);
    }
  }

  return (
    <ul className="evidence-list" aria-label={label}>
      {cleanIds.map((id) => (
        <li key={id}>
          <code>{id}</code>
          <button
            className="copy-button"
            type="button"
            onClick={() => void copyEvidence(id)}
            aria-label={`Copy evidence observation ${id}`}
          >
            {copiedId === id ? "Copied" : "Copy"}
          </button>
        </li>
      ))}
    </ul>
  );
}
