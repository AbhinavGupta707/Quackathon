# Afferens Memory Guardian

Afferens Memory Guardian is a live physical-perception product for the Quackathon Hardware / Physical Perception track.

It uses a live Afferens Vision Node to perceive a real scene, persist evidence-backed object memories, show a memory console, and prepare for object-location questions and verified resolution workflows.

This is an assistive prototype. It is not a medical device, diagnostic system, emergency-response service, certified fall detector, or substitute for human supervision.

## Current State

Implemented on `main`:

- FastAPI backend with `/api/health`, `/api/afferens/status`, `/api/afferens/latest`, `/api/perception/sync`, `/api/observations/latest`, `/api/objects/last-seen`, and `/api/tasks`.
- Durable data spine models for raw Afferens events, normalized observations, detected objects, last-seen memory, queries, tasks, alerts, actuation attempts, verification checks, and status events.
- Postgres + pgvector local Compose service.
- Next.js memory console with live status, sync action, latest observation/evidence display, object memory table, ask UI states, and active task console.

Still pending:

- Backend `/api/query`.
- Backend `/api/alerts`.
- LangGraph object-recovery and verified-resolution workflow.
- Fireworks structured reasoning adapter.
- Task verification/resolution and alert acknowledgement endpoints.

The frontend already has UI seams for query and alert flows, but those backend endpoints are expected to return unavailable until the next backend workflow lane lands.

## Live-Only Rule

Runtime product flows must use live Afferens perception.

- Do not serve cached, replayed, or fixture perception as if it were live.
- Fixtures are allowed only in tests.
- If no live Afferens Node is active, the app must show an honest no-live-node state.
- Answers, tasks, and alerts must cite evidence IDs or say evidence is insufficient.
- Domain-specific AI providers may enrich classification or reasoning, but Afferens remains the live physical evidence gate.

Diagnose Afferens issues in layer order:

1. Confirm API key configuration without revealing the key.
2. Confirm Afferens account/key status.
3. Confirm node setup at <https://afferens.com/node>.
4. Confirm live `/api/perception` availability through backend status/latest calls.
5. Only then debug camera permissions, runtime parsing, or downstream UI behavior.

## Quick Start

Prerequisites:

- Docker Desktop or another Docker Compose compatible runtime.
- Python 3.11+.
- Node.js 20+.
- An Afferens account, API key, and live node from <https://afferens.com/node>.

Create local configuration:

```bash
cp .env.example .env
```

Edit `.env` locally and set at least:

```text
AFFERENS_API_KEY=...
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/afferens_memory_guardian
DATABASE_ENABLED=true
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

Do not commit `.env`, print API keys, or include secrets in screenshots.

Start Postgres + pgvector:

```bash
docker compose up -d postgres
```

Install and test the backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"
python -m pytest
```

Run migrations:

```bash
alembic upgrade head
```

Start the API:

```bash
uvicorn app.main:app --reload
```

Install and run the frontend in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:3000>.

## Local Checks

Backend:

```bash
cd backend
python -m pytest
```

Frontend:

```bash
cd frontend
npm run lint
npm run typecheck
npm run build
```

Docs and whitespace:

```bash
git diff --check
```

## Optional Live Afferens Smoke Test

Only run this when you are ready for manual live testing.

1. Start Postgres.
2. Install backend and frontend dependencies.
3. Add local `.env` keys without exposing them.
4. Start the backend and frontend.
5. Open <https://afferens.com/node> on a phone, laptop, or USB-webcam setup.
6. Start a live Vision node.
7. Click sync in the memory console, or call:

```bash
curl -X POST http://localhost:8000/api/perception/sync \
  -H "Content-Type: application/json" \
  -d '{"limit":1,"room_id":"default_home_zone"}'
```

8. Confirm latest observation and last-seen objects populate from live evidence.
9. Once `/api/query` lands, ask one object-location question such as "Where are my keys?"

## Afferens Node Choices

Phone, laptop webcam, and USB webcam nodes are all valid. The product should stay node-agnostic.

- Laptop webcam: acceptable for a wider fixed field of view, especially if the laptop can see the whole table or counter.
- Phone: often easier to position close to objects or move between rooms during a hackathon demo.
- USB webcam: useful when the laptop needs to stay free and the camera needs a stable angle.

You do not need to grant camera permissions until manual live testing. Before debugging permissions, first confirm the key, account, node activation flow, and backend live status.

## Environment Variables

Documented variables are in [.env.example](.env.example).

| Variable | Scope | Notes |
| --- | --- | --- |
| `ENVIRONMENT` | Backend | Local default is `development`. |
| `APP_VERSION` | Backend | Optional override for health metadata. |
| `AFFERENS_API_KEY` | Backend secret | Required for live Afferens perception. |
| `AFFERENS_BASE_URL` | Backend | Defaults to `https://afferens.com`. |
| `AFFERENS_TIMEOUT_SECONDS` | Backend | HTTP timeout for Afferens calls. |
| `AFFERENS_POLL_INTERVAL_SECONDS` | App config | Development poll cadence for status/sync surfaces. |
| `DATABASE_URL` | Backend secret-ish local config | Required for durable memory. Use the local Compose URL for development. |
| `DATABASE_ENABLED` | Backend | Set `true` for the current product flow. |
| `DATABASE_CONNECT_TIMEOUT_SECONDS` | Backend | Database health/session connection timeout. |
| `FIREWORKS_API_KEY` | Backend secret | Needed once reasoning workflow lands. |
| `FIREWORKS_BASE_URL` | Backend | Fireworks OpenAI-compatible endpoint. |
| `FIREWORKS_MODEL` | Backend | Model ID selected by the workflow lane. |
| `LANGSMITH_TRACING` | Backend optional | Optional tracing for LangGraph development. |
| `LANGSMITH_API_KEY` | Backend optional secret | Only needed when tracing is enabled. |
| `LANGSMITH_PROJECT` | Backend optional | Local trace project name. |
| `NEXT_PUBLIC_API_BASE_URL` | Frontend public | Browser-visible backend base URL. Never put secrets here. |
| `DEMO_MODE` | Tests/docs guardrail | Keep `false` for product runtime. Fixtures belong in tests only. |

## Architecture And Contracts

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) describes the service boundaries and live evidence loop.
- [docs/API_CONTRACT.md](docs/API_CONTRACT.md) defines the shared response shapes.
- [docs/LOCAL_DEVELOPMENT.md](docs/LOCAL_DEVELOPMENT.md) has a command-oriented local setup guide.
- [docs/IMPLEMENTATION_ORCHESTRATION_PLAN.md](docs/IMPLEMENTATION_ORCHESTRATION_PLAN.md) tracks checkpoint sequencing and worktree orchestration.

## Orchestration Note

This project is coordinated through actual Codex worktree sessions with isolated ownership. Do not use sub-agents for implementation work.

An accidental sub-agent run was quarantined in a Git stash named `quarantine subagent output from wrong orchestration mode`. Do not inspect, apply, or integrate that stash unless the user explicitly asks.
