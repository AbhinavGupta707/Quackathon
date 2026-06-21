# Architecture

Afferens Memory Guardian is designed as a live physical-world assistance system, not a passive camera dashboard and not a chatbot over saved media.

The core requirement is that runtime product state comes from live Afferens perception. The system may remember, reason over, and cite prior observations, but it must not present cached, replayed, or fixture data as current physical perception.

## Product Loop

```text
Afferens Node
  -> Afferens API
  -> backend status/latest/sync
  -> immutable raw event ledger
  -> normalized observations
  -> object memory, safety tasks, query workflows
  -> user or caregiver action
  -> live verification check
  -> resolved, escalated, or left open with evidence
```

This loop is the product. Alerts and answers should be treated as intermediate steps until the physical state is verified or a human explicitly acknowledges the unresolved state.

## Service Boundaries

### Afferens Node

The node supplies live physical perception. Valid node options include phone, laptop webcam, and USB webcam setups supported by Afferens. The product must not require a specific device form factor.

### Afferens API

Afferens is the primary physical evidence source. Backend calls should use server-side credentials only and must never return the API key or any key fragment to the frontend.

The activation/debug sequence is:

1. Key configured.
2. Account/key accepted.
3. Node active through <https://afferens.com/node>.
4. Live `/api/perception` available.
5. Runtime parsing and downstream product logic.

### Backend

The backend owns all secret-bearing work and all durable state.

Checkpoint 1 backend boundaries:

- Configuration loading without secret exposure.
- `/api/health`.
- Afferens status mapping.
- Latest live Afferens event fetch.
- Honest no-live-node and provider-error states.

Checkpoint 2+ backend boundaries:

- Raw event persistence.
- Observation normalization.
- Object memory updates.
- Query routing and answer synthesis.
- LangGraph task workflows.
- Fireworks structured-output calls.
- Safety rules, actuation logging, and verification checks.
- SSE/WebSocket or polling-friendly event stream.

### Database

Postgres is the primary durable store. `pgvector` is reserved for semantic memory once query workflows need embeddings or nearest-neighbor retrieval.

Expected durable tables:

- `afferens_raw_events`
- `observations`
- `detected_objects`
- `last_seen_objects`
- `queries`
- `tasks`
- `task_events`
- `alerts`
- `actuation_attempts`
- `verification_checks`
- `system_status_events`

Raw Afferens events should be immutable. Normalized observations are derived from raw events and can be regenerated if parser logic improves.

### Frontend

The frontend is an operational UI for setup, live status, evidence, questions, tasks, and caregiver review. It must not hold provider secrets.

Expected areas:

- Setup/status page.
- Live dashboard.
- Ask interface.
- Active task console.
- Caregiver alerts.
- Evidence inspector.

When no live node is available, the frontend should say so plainly and guide the user through official Afferens activation before suggesting camera or runtime debugging.

## Live Perception Flow

Checkpoint 1:

```text
frontend status page
  -> backend /api/health and /api/afferens/status
  -> backend checks key presence and Afferens state
  -> optional /api/afferens/latest fetches the latest live event
  -> UI displays missing_key, invalid_key, inactive_key, no_live_events, live, or error
```

Checkpoint 2:

```text
POST /api/perception/sync
  -> fetch live Afferens Vision events
  -> persist raw events
  -> normalize observations
  -> update last_seen_objects
  -> create or update tasks when evidence supports it
  -> return observation IDs and updated memory/task summaries
```

Checkpoint 3:

```text
live observation
  -> deterministic safety rule
  -> conservative explanation
  -> alert/action
  -> later live observation
  -> verification result
  -> resolved, failed_verification, waiting_for_human, or escalated
```

## Durable Event Ledger Direction

The raw event ledger is the evidence root. Every user-facing answer, alert, or task should be traceable to one or more observation IDs, and those observations should trace back to raw Afferens event IDs.

Design rules:

- Store raw provider payloads in `afferens_raw_events`.
- Preserve provider timestamps, source node ID, modality, and event ID when present.
- Add ingestion timestamps for backend receipt time.
- Normalize into stable internal `observations`.
- Keep parser version or normalizer version once normalization evolves.
- Do not mutate raw event rows to "fix" interpretation.
- Store later corrections as new derived rows or task events.

## LangGraph Placement

LangGraph starts in Checkpoint 2. It should not be required for Checkpoint 1 live ingestion or Afferens status/debug flows.

Use LangGraph for lifecycle state, not for basic provider plumbing:

- Object recovery lifecycle.
- Safety alert lifecycle.
- Caregiver acknowledgement lifecycle.
- Verified resolution lifecycle.

The graph should move tasks through explicit states such as `open`, `waiting_for_human`, `actuation_attempted`, `verification_pending`, `verified_resolved`, `escalated`, `dismissed`, and `failed_verification`.

## Fireworks Placement

Fireworks AI is the primary LLM/structured-output provider starting in Checkpoint 2.

Use Fireworks for:

- Query intent routing.
- Evidence sufficiency checks.
- Answer synthesis.
- Conservative safety explanation wording.

Do not use Fireworks as a prerequisite for:

- Reading configuration.
- Fetching live Afferens status.
- Persisting raw events.
- Normalizing straightforward provider payloads.
- Showing no-live-node state.

Fireworks should reason over structured observations by default. Raw frame or image upload to any vision model should be opt-in, privacy-gated, and traceable to live Afferens evidence.

## Safety Principles

Use conservative language:

- possible
- appears
- may need checking
- human verification required

Avoid claims of:

- diagnosis
- medical-device behavior
- emergency response
- certified fall detection
- autonomous monitoring

Safety alerts should tell a human what evidence was seen and what action may need checking. A safety task is not complete until live verification, explicit human resolution, dismissal, or escalation is recorded.

## Privacy Principles

- Keep provider keys server-side.
- Do not expose `.env` or `AFFERENS_API_KEY`.
- Store the minimum evidence needed for the demo and product loop.
- Prefer structured events over continuous raw video storage.
- Make optional external enrichment providers explicit.
- Preserve source attribution so users can distinguish live Afferens evidence from later interpretation.

## Failure Modes

Expected provider states are product states, not exceptions to hide:

- Missing key.
- Invalid key.
- Inactive key.
- No active node or no live events.
- Provider timeout/error.
- Malformed provider payload.
- No object currently visible.
- Evidence insufficient for a confident answer.

The UI and API should represent these states honestly.
