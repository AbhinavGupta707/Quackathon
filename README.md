# Afferens Memory Guardian

Afferens Memory Guardian is a live physical-perception product for the Quackathon Hardware / Physical Perception track.

It is a home-assistance agent that uses a live Afferens Vision Node to perceive a real scene, remember evidence-backed object locations, answer memory questions, raise conservative caregiver-facing alerts, and verify resolution through later live perception whenever possible.

The product loop is:

```text
live Afferens perception
  -> raw evidence ledger
  -> normalized observations
  -> object memory, safety, and task workflows
  -> user or caregiver action
  -> later live Afferens verification
  -> resolved, escalated, or left open with evidence
```

This is an assistive prototype. It is not a medical device, diagnostic system, emergency-response service, certified fall detector, or substitute for human supervision.

## Current Status

Checkpoint 1 is focused on the live Afferens spine and developer experience:

- Backend scaffold and Afferens status/latest endpoints.
- Frontend setup/status UI.
- Postgres/pgvector local service.
- Docs that explain the live-only product boundary.

Backend and frontend folders may be created by parallel worktree sessions. Until they land, this repository contains the shared planning docs, API contract, environment example, and local database Compose file.

## Architecture

Target stack:

```text
Afferens Node
(phone, laptop webcam, or USB webcam)
      |
      v
Afferens API
      |
      v
FastAPI Backend
  - config and health
  - Afferens adapter
  - raw event ledger
  - observation normalizer
  - object memory service
  - LangGraph task workflows from Checkpoint 2
  - Fireworks reasoning adapter from Checkpoint 2
  - safety, actuation, verification
  - realtime stream
      |
      v
Postgres + pgvector
      |
      v
Next.js Frontend
  - setup/status
  - live dashboard
  - ask interface
  - active task console
  - caregiver alerts
  - evidence inspector
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for service boundaries, data flow, safety principles, and checkpoint placement for LangGraph and Fireworks.

## Live-Only Afferens Requirement

Runtime product flows must use live Afferens perception.

- Do not serve cached, replayed, or fixture perception as if it were live.
- Fixtures are allowed only in tests.
- If no live Afferens Node is active, the app must show an honest no-live-node state.
- User-facing answers and alerts must cite evidence IDs or say evidence is insufficient.
- Domain-specific AI providers may enrich classification or reasoning, but Afferens remains the live physical evidence gate.

Diagnose Afferens issues in layer order:

1. Confirm API key configuration without revealing the key.
2. Confirm Afferens account/key status.
3. Confirm node setup at <https://afferens.com/node>.
4. Confirm live `/api/perception` availability.
5. Only then debug camera permissions, runtime parsing, or downstream logic.

## Afferens Node Options

The product must be node-agnostic. Any live Afferens Vision Node can be valid:

- Phone browser opened to <https://afferens.com/node>.
- Laptop webcam through the Afferens Node flow.
- USB webcam through an Afferens-supported node setup.

For a hackathon demo, a phone on a small stand is often the easiest physical setup because the scene can be aimed at a controlled table or counter. Do not hard-code the product to require a phone.

## Local Setup

Prerequisites:

- Git.
- Docker Desktop or another Docker Compose compatible runtime.
- Python 3.11+ once `backend/` exists.
- Node.js 20+ once `frontend/` exists.
- An Afferens account, API key, and live node.

Create local configuration:

```bash
cp .env.example .env
```

Then edit `.env` locally and set `AFFERENS_API_KEY`. Never commit `.env` and never print the key in logs, screenshots, docs, or issue reports.

Start the local Postgres/pgvector service:

```bash
docker compose up -d postgres
```

Backend, once `backend/` exists:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
```

Then install using the dependency file provided by that workstream:

```bash
pip install -e ".[dev]"
```

or:

```bash
pip install -r requirements.txt
```

Run the backend using the command documented by the backend workstream. The expected development shape is:

```bash
uvicorn app.main:app --reload
```

Frontend, once `frontend/` exists:

```bash
cd frontend
npm install
npm run dev
```

More detail lives in [docs/LOCAL_DEVELOPMENT.md](docs/LOCAL_DEVELOPMENT.md).

## Environment Variables

Documented variables are in [.env.example](.env.example).

| Variable | Required | Notes |
| --- | --- | --- |
| `AFFERENS_API_KEY` | Yes | Server-side only. Never expose or log it. |
| `AFFERENS_BASE_URL` | Yes | Defaults to `https://afferens.com`. |
| `AFFERENS_POLL_INTERVAL_SECONDS` | Yes | Poll cadence for development status/sync flows. |
| `DEMO_MODE` | No | Keep `false` for product runtime. Fixture data is for tests only. |
| `DATABASE_URL` | Expected later | Backend should point at Postgres/pgvector when database code lands. |
| `FIREWORKS_API_KEY` | Checkpoint 2 | Server-side only, for structured reasoning after live ingestion works. |

## API Contract

The shared API contract is [docs/API_CONTRACT.md](docs/API_CONTRACT.md). Backend and frontend workstreams should implement against it and propose changes rather than independently changing endpoint names or response shapes.

Checkpoint 1 must not depend on LangGraph or Fireworks availability. Live Afferens ingestion, health, status, and latest-event visibility should work deterministically first.

## Checkpoint Roadmap

### Checkpoint 1: Live Afferens Spine

- Backend and frontend scaffolds.
- Postgres/pgvector local service.
- `/api/health`.
- `/api/afferens/status`.
- `/api/afferens/latest`.
- Setup/status UI that distinguishes missing key, invalid key, inactive key, no live events, and live events.
- No runtime cached perception paths.

### Checkpoint 2: Evidence-Backed Memory Product

- Immutable raw event ledger.
- Normalized observations.
- Last-seen object memory.
- `/api/perception/sync`.
- `/api/objects/last-seen`.
- `/api/query`.
- LangGraph object-recovery workflow.
- Fireworks query routing, evidence sufficiency checks, and answer synthesis.
- Active task console and verified resolution path.

### Checkpoint 3: Safety, Actuation, And Hardening

- Safety rules from live observations.
- Conservative caregiver alerts.
- Browser/dashboard alarm and optional Afferens actuation.
- Verification checks that close or escalate tasks based on later live perception.
- Evidence inspector.
- Realtime updates or robust polling.
- Broader tests and documentation.

### Optional Checkpoint 4: Live CV Enrichment

- Live-only local CV enrichment if Afferens labels are too coarse.
- Enrichment records remain traceable to live Afferens observations.
- Afferens remains the primary evidence gate.

## Orchestration Note

This project is coordinated through actual Codex worktree sessions with isolated branches. Do not use sub-agents for implementation work.

An accidental sub-agent run was quarantined in a Git stash named `quarantine subagent output from wrong orchestration mode`. Do not inspect, apply, or integrate that stash unless the user explicitly asks.
