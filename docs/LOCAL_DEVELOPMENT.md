# Local Development

This guide is the local runbook for Afferens Memory Guardian.

Runtime product flows must use live Afferens perception. Fixtures and replay data are allowed only in tests.

## What Exists Today

Current backend:

- `/api/health`
- `/api/afferens/status`
- `/api/afferens/latest`
- `/api/perception/sync`
- `/api/observations/latest`
- `/api/objects/last-seen`
- `/api/tasks`
- `/api/query`
- `/api/alerts`
- `/api/tasks/{task_id}/verify`
- `/api/tasks/{task_id}/resolve`
- `/api/alerts/{alert_id}/ack`
- SQLAlchemy models for the raw event ledger, observations, object memory, queries, tasks, alerts, actuation attempts, verification checks, and status events.
- Alembic durable schema migration.
- Fireworks structured reasoning adapter with deterministic fallback.
- LangGraph object-recovery workflow wrapper with deterministic fallback.

Current frontend:

- Live provider/database status.
- Manual live perception sync.
- Latest observation and evidence display.
- Object memory table.
- Ask UI backed by `/api/query`.
- Alert queue backed by `/api/alerts`.
- Active task console.

Pending product work:

- Frontend task verify/resolve and alert acknowledgement controls.
- Alarm actuation endpoint.
- Streaming event updates.
- Full manual live Afferens plus Fireworks smoke test.

## Rules Of The Road

- Never print, inspect, expose, commit, or transmit `.env` contents or `AFFERENS_API_KEY`.
- Use `.env.example` for documented configuration.
- Keep `DEMO_MODE=false` for product runtime.
- If no live Afferens Node is active, the product should show a no-live-node state.
- Start Afferens debugging with registration, activation, and live API state before camera permissions or app runtime logic.

## Prerequisites

- Docker Desktop or compatible Docker Compose runtime.
- Python 3.11+.
- Node.js 20+.
- An Afferens account and API key.
- A live Afferens Node from <https://afferens.com/node> for manual live testing.

## Environment

Create a local env file:

```bash
cp .env.example .env
```

Edit `.env` locally. Required for the current data spine:

```text
AFFERENS_API_KEY=...
DATABASE_ENABLED=true
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/afferens_memory_guardian
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

Recommended for Checkpoint 2 query workflow work:

```text
FIREWORKS_API_KEY=...
FIREWORKS_BASE_URL=https://api.fireworks.ai/inference/v1
FIREWORKS_MODEL=...
LANGSMITH_TRACING=false
LANGSMITH_PROJECT=afferens-memory-guardian-local
```

Only set `LANGSMITH_API_KEY` if you enable tracing.

## Database

Start Postgres with pgvector:

```bash
docker compose up -d postgres
```

Check container health:

```bash
docker compose ps postgres
```

Stop local services:

```bash
docker compose down
```

The default local connection is:

```text
postgresql://postgres:postgres@localhost:5432/afferens_memory_guardian
```

## Backend

Install:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"
```

Run tests:

```bash
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

Useful local checks:

```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/afferens/status
curl http://localhost:8000/api/afferens/latest
curl http://localhost:8000/api/observations/latest
curl http://localhost:8000/api/objects/last-seen
curl http://localhost:8000/api/tasks
curl http://localhost:8000/api/alerts
```

Manual sync, after a live Afferens Node is active:

```bash
curl -X POST http://localhost:8000/api/perception/sync \
  -H "Content-Type: application/json" \
  -d '{"limit":1,"room_id":"default_home_zone"}'
```

Do not use mocked Afferens responses through product endpoints. Tests may mock provider responses.

Evidence-backed query:

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query":"Where are my keys?","session_id":"local-smoke"}'
```

Task verification and resolution:

```bash
curl -X POST http://localhost:8000/api/tasks/<task_id>/verify \
  -H "Content-Type: application/json" \
  -d '{"room_id":"default_home_zone"}'

curl -X POST http://localhost:8000/api/tasks/<task_id>/resolve \
  -H "Content-Type: application/json" \
  -d '{"resolved_by":"user","resolution_note":"I found it."}'
```

Alert acknowledgement:

```bash
curl -X POST http://localhost:8000/api/alerts/<alert_id>/ack \
  -H "Content-Type: application/json" \
  -d '{"acknowledged_by":"caregiver","note":"Checking now."}'
```

## Frontend

Install:

```bash
cd frontend
npm install
```

Run checks:

```bash
npm run lint
npm run typecheck
npm run build
```

Start the frontend:

```bash
npm run dev
```

Open <http://localhost:3000>.

The frontend reads `NEXT_PUBLIC_API_BASE_URL`. This value is public in browser JavaScript and must not contain secrets.

## Afferens Node Setup

Use the official activation flow first:

1. Confirm `.env` has `AFFERENS_API_KEY` set without printing it.
2. Confirm the Afferens account/key is active.
3. Open <https://afferens.com/node>.
4. Start a live Vision node from a phone, laptop webcam, or USB webcam setup.
5. Confirm `/api/afferens/status` reports a live or no-live-events state accurately.
6. Confirm `/api/afferens/latest` returns event metadata without exposing secrets.
7. Only then debug camera permissions, parsing, or downstream UI behavior.

Device tradeoffs:

- Laptop webcam: good for a stable, wider view of a table or counter.
- Phone: easy to aim at close objects or move between rooms.
- USB webcam: good for a fixed demo angle while keeping the laptop free.

No camera permission is needed until manual live testing.

## Next Manual Test Checklist

Use this checklist after keys are available and the live node is ready:

1. Start the database with `docker compose up -d postgres`.
2. Install backend deps with `pip install -e ".[test]"`.
3. Install frontend deps with `npm install`.
4. Add local `.env` keys and database settings.
5. Run `alembic upgrade head`.
6. Start the backend with `uvicorn app.main:app --reload`.
7. Start the frontend with `npm run dev`.
8. Start a live Afferens Vision node.
9. Sync perception from the memory console.
10. Confirm latest observation and object memory populate from live evidence.
11. Ask one object-location question and confirm the answer cites observation evidence.
12. If a recovery task opens, put the object back in view and call task verification.

## Troubleshooting Order

If Afferens appears missing or unavailable:

1. Check that the feature is actually registered or implemented in the current repo.
2. Check `.env` configuration without revealing secret values.
3. Check account/key status.
4. Check <https://afferens.com/node> setup.
5. Check live `/api/perception` availability through backend status/latest.
6. Debug camera permissions.
7. Debug backend parsing.
8. Debug frontend rendering.

## Quarantined Output

An accidental sub-agent output stash exists with the name `quarantine subagent output from wrong orchestration mode`.

Do not inspect, apply, or integrate that stash unless the user explicitly asks for salvage or review.
