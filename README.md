# Afferens Memory Guardian

Afferens Memory Guardian is a live physical-perception system for helping patients and caregivers understand what is happening in a home environment. It combines a live Afferens Vision Node, durable object memory, action intelligence, reasoning workflows, and caregiver review surfaces into one product loop: perceive the room, store cited evidence, reason about what matters, act carefully, and verify outcomes later from fresh live observations.

The system is designed for assistive memory and caregiver review. It is not a medical device, diagnostic system, emergency-response service, certified fall detector, or replacement for human supervision.

## Product Capabilities

- Live Afferens ingestion with provider status, latest-observation sync, redacted health checks, and honest no-live-node states.
- Durable object memory that tracks observations, last-seen locations, region context, evidence IDs, and stale-current distinctions.
- Patient-facing memory assistance for questions such as where an object was last seen, with answers grounded in cited observations.
- Active task flows for finding objects, verifying resolution from later live perception, and allowing explicit human resolution when appropriate.
- Caregiver dashboard for alerts, action candidates, evidence review, home region calibration, daily care notes, wellness checks, and family-message prompts.
- Live action intelligence for hydration candidates using browser pose/hand telemetry plus Afferens object context. Bottle, cup, or water visibility alone does not count as intake.
- Conservative possible-fall candidate handling with local YOLO readiness checks, persistence/debounce rules, and caregiver escalation language.
- Provider readiness views for Afferens, Fireworks, LangSmith, semantic memory, optional visual enrichment providers, local action runtime, and privacy settings.
- Disabled-by-default assistive actuation for alarm and frame-capture commands, with every attempt logged and tied to a task or alert.
- Semantic memory with lexical fallback and optional vector retrieval for cited, evidence-backed recall.

## Architecture

```mermaid
flowchart LR
  node["Afferens Node"] --> backend["FastAPI backend"]
  browser["Browser Action Node"] --> backend
  backend --> db["Postgres + pgvector"]
  backend --> workflows["LangGraph workflows"]
  backend --> providers["Fireworks / provider adapters"]
  backend --> frontend["Next.js patient UI"]
  backend --> caregiver["Next.js caregiver UI"]
  caregiver --> actuation["Afferens actuation commands"]
```

- `backend/app`: FastAPI routes, Afferens adapter, normalization, repositories, action intelligence, workflows, provider status, and safety/actuation services.
- `backend/alembic`: migrations for durable observations, object memory, home regions, daily care, action events, runtime monitor state, and semantic retrieval.
- `backend/tests`: focused route, workflow, safety, provider, action-intelligence, and persistence tests.
- `frontend/app`: Next.js routes for patient mode, caregiver review, and caregiver access.
- `frontend/components`: patient/caregiver panels, action review, evidence, wellness, semantic memory, and provider readiness UI.
- `frontend/lib`: API client, action telemetry, hydration finite-state machine, lazy MediaPipe pose/hand runtime, and shared types.
- `frontend/scripts`: static checks for hydration semantics and MediaPipe lazy-loading, plus local MediaPipe asset setup.
- `scripts`: provider redaction smoke and local YOLO fall-model validator.

## Live-Only Runtime

Runtime product behavior must be grounded in live Afferens perception and live browser action telemetry.

- Fixtures are allowed only in tests.
- If a live Afferens Node is unavailable, the product should show that state directly.
- Object visibility can provide context, but hydration requires temporal action evidence.
- Fall checks require model-backed or action-backed evidence plus persistence, then caregiver verification.
- AI provider output may enrich reasoning, but it must not replace Afferens as the physical evidence gate.
- Raw video frames are not persisted by default.

## Prerequisites

- Python 3.11 or newer.
- Node.js 20 or newer.
- Docker Desktop or another Docker Compose compatible runtime.
- An Afferens account, API key, and live node from [afferens.com/node](https://afferens.com/node).

## Local Setup

Create local configuration from the checked-in template:

```bash
cp .env.example .env
```

Set at least these local values without committing secrets:

```text
AFFERENS_API_KEY=...
DATABASE_ENABLED=true
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/afferens_memory_guardian
```

Start Postgres:

```bash
docker compose up -d postgres
```

Install the backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal, install and run the frontend:

```bash
cd frontend
npm install
npm run dev
```

`npm run dev` and `npm run build` prepare the browser MediaPipe assets automatically.

Open the product surfaces:

- Patient mode: [localhost:3000](http://localhost:3000)
- Caregiver review: [localhost:3000/caregiver](http://localhost:3000/caregiver)
- Afferens node setup: [afferens.com/node](https://afferens.com/node)

If the backend is not running on `http://localhost:8000`, create `frontend/.env.local` locally:

```text
NEXT_PUBLIC_API_BASE_URL=http://localhost:<backend-port>
```

Restart the frontend after changing public frontend environment values.

## Configuration

Important runtime variables:

| Variable | Purpose |
| --- | --- |
| `AFFERENS_API_KEY` | Server-side key for live Afferens perception. |
| `AFFERENS_BASE_URL` | Afferens API base URL, defaulting to `https://afferens.com`. |
| `DATABASE_URL` | Postgres connection string for durable memory and tasks. |
| `FIREWORKS_API_KEY` | Optional structured reasoning provider key. |
| `LANGSMITH_TRACING` / `LANGSMITH_API_KEY` | Optional workflow tracing. |
| `SEMANTIC_MEMORY_ENABLED` | Enables semantic retrieval surfaces when configured. |
| `ACTION_YOLO_FALL_ENABLED` | Enables local YOLO fall-runtime validation and inference when a compatible model is configured. |
| `ACTION_YOLO_FALL_MODEL_PATH` | Local path to a compatible fall model. Model weights are not tracked. |
| `ACTION_RAW_VIDEO_STORAGE_ENABLED` | Defaults to `false`; raw frames should stay off unless explicitly reviewed. |
| `NEXT_PUBLIC_API_BASE_URL` | Browser-visible backend URL. Never put secrets in `NEXT_PUBLIC_` values. |
| `CAREGIVER_ACCESS_ENABLED` | Optional lightweight caregiver route gate. |
| `CAREGIVER_PASSCODE` | Server-side passcode for the caregiver gate. |
| `FIXTURE_MODE` | Test-only guardrail; keep disabled for runtime use. |

## Verification

Run the backend suite:

```bash
cd backend
python -m pytest
```

Run frontend checks:

```bash
cd frontend
npm run lint
npm run typecheck
npm run check:hydration-fsm
npm run check:mediapipe-lazy
npm run build
```

Run focused repository-level smoke checks from the repository root:

```bash
backend/.venv/bin/python scripts/smoke_provider_redaction.py
backend/.venv/bin/python scripts/validate_yolo_fall_model.py
git diff --check
```

Manual live checks should confirm:

- `/api/health` redacts secrets and shows provider readiness.
- `/api/afferens/status` and `/api/afferens/latest` reflect a running Afferens Node.
- Patient object memory updates after a live sync and answers cite evidence IDs.
- Caregiver review opens at `/caregiver` and shows alerts, wellness checks, action candidates, and evidence.
- The Action Node lazy-loads MediaPipe only after starting.
- Hydration candidates require hand/object/mouth temporal evidence plus Afferens object context.
- Possible-fall candidates use configured model/action evidence, persistence, and caregiver escalation wording.
- Actuation remains disabled unless deliberately configured and tested against a safe live node.

## Repository Hygiene

Tracked files are limited to product runtime, tests, setup scripts, deployment configuration, and this README. The repository should not include local secrets, frontend local environment files, generated build output, local model weights, MediaPipe downloaded assets, shell history, personal notes, or handoff material.
