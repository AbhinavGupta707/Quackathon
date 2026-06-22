"use client";

import { formatDateTime, sentenceCase } from "@/lib/format";
import type {
  AfferensStatus,
  Loadable,
  ProvidersStatusResponse,
  RuntimeMonitorStatus
} from "@/lib/types";
import { StateBlock } from "./StateBlock";
import { StatusPill, type StatusTone } from "./StatusPill";

type ProviderReadinessPanelProps = {
  afferens: Loadable<AfferensStatus>;
  homeMemory?: Loadable<{ monitor: RuntimeMonitorStatus; message?: string | null }>;
  providers: Loadable<ProvidersStatusResponse>;
  variant: "patient" | "caregiver";
};

export function ProviderReadinessPanel({
  afferens,
  homeMemory,
  providers,
  variant
}: ProviderReadinessPanelProps) {
  if (variant === "patient") {
    return (
      <PatientReadinessPanel afferens={afferens} homeMemory={homeMemory} providers={providers} />
    );
  }

  return <CaregiverProviderPanel providers={providers} />;
}

function PatientReadinessPanel({
  afferens,
  homeMemory,
  providers
}: Omit<ProviderReadinessPanelProps, "variant">) {
  const providerList = providers.data?.providers ?? [];
  const fireworks = providerById(providerList, "fireworks");
  const semanticMemory = providerById(providerList, "semantic_memory");
  const monitor = homeMemory?.data?.monitor ?? null;
  const memoryRunning = monitor ? ["running", "degraded"].includes(monitor.state) : false;
  const liveConnected = afferens.data?.state === "live";
  const helperReady = fireworks ? providerCanEnhanceAnswers(fireworks.state) : false;

  return (
    <section className="patient-panel patient-readiness-panel" aria-labelledby="patient-readiness-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Ready To Help</p>
          <h2 id="patient-readiness-title">What I can use right now</h2>
        </div>
        <StatusPill
          label={liveConnected && memoryRunning ? "Home ready" : liveConnected ? "Live view ready" : "Needs setup"}
          tone={liveConnected && memoryRunning ? "good" : liveConnected ? "info" : "warn"}
        />
      </div>

      <div className="readiness-steps" aria-label="Patient readiness summary">
        <ReadinessStep
          body={homeMemoryCopy(monitor, homeMemory?.error)}
          label="Home memory"
          tone={memoryRunning ? "good" : homeMemory?.error ? "warn" : "quiet"}
          value={memoryRunning ? "On" : "Off"}
        />
        <ReadinessStep
          body={afferens.data?.message || afferens.error || "Checking for the live home view."}
          label="Live home view"
          tone={liveConnected ? "good" : afferens.error ? "bad" : "warn"}
          value={liveConnected ? "Connected" : "Waiting"}
        />
        <ReadinessStep
          body={helperReady ? "A model helper may improve wording when evidence is cited." : "I will use the local evidence fallback when model help is not ready."}
          label="Answer help"
          tone={helperReady ? "good" : "info"}
          value={helperReady ? "Enhanced" : "Fallback"}
        />
        <ReadinessStep
          body={semanticMemoryCopy(semanticMemory?.state)}
          label="Memory search"
          tone={semanticMemoryTone(semanticMemory?.state)}
          value={semanticMemoryPatientValue(semanticMemory?.state)}
        />
      </div>

      <div className="patient-question-guide" aria-label="Question ideas">
        <strong>Try asking:</strong>
        <div>
          <span>Where are my keys?</span>
          <span>What happened this morning?</span>
          <span>What should I remember from today?</span>
          <span>Did I leave anything important out?</span>
        </div>
      </div>
    </section>
  );
}

function CaregiverProviderPanel({ providers }: { providers: Loadable<ProvidersStatusResponse> }) {
  const providerList = providers.data?.providers ?? [];
  const afferens = providerById(providerList, "afferens");
  const fireworks = providerById(providerList, "fireworks");
  const langsmith = providerById(providerList, "langsmith");
  const semanticMemory = providerById(providerList, "semantic_memory");
  const gemini = providerById(providerList, "gemini");
  const parcle = providerById(providerList, "parcle") ?? providerById(providerList, "parcel");

  return (
    <section className="review-card provider-readiness-panel" aria-labelledby="provider-readiness-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Provider Readiness</p>
          <h2 id="provider-readiness-title">Evidence and answer layers</h2>
        </div>
        <StatusPill
          label={providers.loading ? "Checking" : providers.error ? "Unavailable" : "Redacted status"}
          tone={providers.error ? "bad" : providers.loading ? "warn" : "info"}
        />
      </div>

      {providers.error ? (
        <StateBlock
          tone="error"
          title="Provider status unavailable"
          body="The backend status endpoint is not reachable. Do not diagnose model/runtime behavior until provider registration is reported."
        />
      ) : null}

      <div className="provider-layer-list" aria-label="Provider layer status">
        <ProviderLayer
          body={afferens?.message || "Afferens status has not been reported yet."}
          label="Live Afferens evidence"
          tone={providerTone(afferens?.state)}
          value={sentenceCase(afferens?.state || (providers.loading ? "checking" : "not reported"))}
        />
        <ProviderLayer
          body={semanticCaregiverCopy(semanticMemory?.state, semanticMemory?.message)}
          label="Semantic retrieval"
          tone={semanticMemoryTone(semanticMemory?.state)}
          value={semanticCaregiverValue(semanticMemory?.state)}
        />
        <ProviderLayer
          body={fireworksCopy(fireworks?.state, fireworks?.message)}
          label="Fireworks synthesis"
          tone={providerTone(fireworks?.state)}
          value={sentenceCase(fireworks?.state || "not reported")}
        />
        <ProviderLayer
          body={langsmith?.message || "Tracing status has not been reported. It is observability only."}
          label="LangSmith tracing"
          tone={langsmith?.state === "configured" ? "good" : langsmith?.state === "disabled" ? "quiet" : "info"}
          value={sentenceCase(langsmith?.state || "not reported")}
        />
        <ProviderLayer
          body={gemini?.message || "Gemini is treated as deferred unless the backend reports a live provider."}
          label="Gemini"
          tone={providerTone(gemini?.state || "deferred")}
          value={sentenceCase(gemini?.state || "deferred")}
        />
        <ProviderLayer
          body={parcle?.message || "Parcle/Parcel memory is treated as deferred unless the backend reports a live provider."}
          label="Parcle or Parcel"
          tone={providerTone(parcle?.state || "deferred")}
          value={sentenceCase(parcle?.state || "deferred")}
        />
      </div>
    </section>
  );
}

function ReadinessStep({
  body,
  label,
  tone,
  value
}: {
  body: string;
  label: string;
  tone: StatusTone;
  value: string;
}) {
  return (
    <div className="readiness-step">
      <span>{label}</span>
      <strong>{value}</strong>
      <p>{body}</p>
      <StatusPill label={statusText(tone)} tone={tone} />
    </div>
  );
}

function ProviderLayer({
  body,
  label,
  tone,
  value
}: {
  body: string;
  label: string;
  tone: StatusTone;
  value: string;
}) {
  return (
    <article className="provider-layer">
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
      <p>{body}</p>
      <StatusPill label={statusText(tone)} tone={tone} />
    </article>
  );
}

function providerById(providers: ProvidersStatusResponse["providers"], id: string) {
  return providers.find((provider) => provider.provider.toLowerCase() === id);
}

function providerCanEnhanceAnswers(state?: string): boolean {
  return ["configured", "live", "ready", "ok"].includes(state || "");
}

function providerTone(state?: string): StatusTone {
  if (["configured", "live", "ready", "ok", "vector_enabled", "pgvector_ready"].includes(state || "")) {
    return "good";
  }
  if (["missing_key", "unavailable", "error", "invalid_key", "inactive_key"].includes(state || "")) {
    return "bad";
  }
  if (["degraded", "lexical", "fallback", "no_live_events"].includes(state || "")) {
    return "warn";
  }
  if (["disabled", "deferred"].includes(state || "")) {
    return "quiet";
  }
  return "quiet";
}

function semanticMemoryTone(state?: string): StatusTone {
  if (["vector_enabled", "pgvector_ready", "hybrid", "pgvector"].includes(state || "")) {
    return "good";
  }
  if (["lexical", "deterministic_lexical", "configured"].includes(state || "")) {
    return "info";
  }
  if (["unavailable", "disabled", "missing_key", "error"].includes(state || "")) {
    return "warn";
  }
  return "quiet";
}

function semanticMemoryCopy(state?: string): string {
  if (["vector_enabled", "pgvector_ready", "hybrid", "pgvector"].includes(state || "")) {
    return "Broader memory matching is reported ready by the backend.";
  }
  if (["lexical", "deterministic_lexical", "configured"].includes(state || "")) {
    return "I can search local notes, but broader vector memory is not reported live.";
  }
  return "Broader memory is unavailable or not reported yet.";
}

function semanticCaregiverCopy(state?: string, message?: string): string {
  if (message) {
    return message;
  }
  if (["vector_enabled", "pgvector_ready", "hybrid", "pgvector"].includes(state || "")) {
    return "Semantic memory can use vector or hybrid retrieval when answers cite evidence.";
  }
  if (["lexical", "deterministic_lexical", "configured"].includes(state || "")) {
    return "Semantic memory is available through local lexical retrieval; vector retrieval is not being claimed live.";
  }
  return "Semantic retrieval is unavailable or not reported. Memory answers should fall back conservatively.";
}

function semanticCaregiverValue(state?: string): string {
  if (["vector_enabled", "pgvector"].includes(state || "")) {
    return "Vector enabled";
  }
  if (["pgvector_ready", "hybrid"].includes(state || "")) {
    return state === "hybrid" ? "Hybrid" : "Pgvector ready";
  }
  if (["lexical", "deterministic_lexical", "configured"].includes(state || "")) {
    return "Lexical fallback";
  }
  return sentenceCase(state || "not reported");
}

function semanticMemoryPatientValue(state?: string): string {
  if (["vector_enabled", "pgvector_ready", "hybrid", "pgvector"].includes(state || "")) {
    return "Broader";
  }
  if (["lexical", "deterministic_lexical", "configured"].includes(state || "")) {
    return "Local";
  }
  return "Waiting";
}

function fireworksCopy(state?: string, message?: string): string {
  if (providerCanEnhanceAnswers(state)) {
    return message || "Fireworks can help phrase answers after local evidence and citations are selected.";
  }
  if (state === "missing_key" || state === "unavailable" || state === "degraded") {
    return message || "Fireworks is not ready, so answers should use deterministic fallback wording.";
  }
  return message || "Fireworks status has not been reported. Do not assume model synthesis is live.";
}

function homeMemoryCopy(monitor: RuntimeMonitorStatus | null, error?: string): string {
  if (error) {
    return "The home memory controls are unavailable. A caregiver can check setup.";
  }
  if (!monitor || ["off", "stopped", "idle"].includes(monitor.state)) {
    return "Turn this on when the live home view is connected.";
  }
  if (monitor.last_error) {
    return `Needs checking: ${monitor.last_error}`;
  }
  if (monitor.last_tick_at) {
    return `Last checked ${formatDateTime(monitor.last_tick_at)}.`;
  }
  return "I can keep checking gently in the background.";
}

function statusText(tone: StatusTone): string {
  if (tone === "good") {
    return "Ready";
  }
  if (tone === "bad") {
    return "Blocked";
  }
  if (tone === "warn") {
    return "Check";
  }
  if (tone === "quiet") {
    return "Waiting";
  }
  return "Info";
}
