# Local Development

This guide describes the intended local development workflow for Afferens Memory Guardian.

The repository may be assembled by parallel worktree sessions. Some folders referenced here, such as `backend/` and `frontend/`, may not exist until their owning sessions land.

## Rules Of The Road

- Runtime product flows must use live Afferens perception.
- Fixtures and replay data are allowed only for tests.
- If no live Afferens Node is active, show a no-live-node state.
- Never print, inspect, expose, commit, or transmit `.env` contents or `AFFERENS_API_KEY`.
- Use `.env.example` for documented configuration.
- Start Afferens debugging with registration, activation, and live API state before camera permissions or app runtime logic.

## Prerequisites

- Docker Desktop or compatible Docker Compose runtime.
- Python 3.11+ for backend development.
- Node.js 20+ for frontend development.
- An Afferens account and API key.
- A live Afferens Node from <https://afferens.com/node>.

## Environment

Create a local env file:

```bash
cp .env.example .env
```

Then edit `.env` locally:

```text
AFFERENS_API_KEY=your_key_here
AFFERENS_BASE_URL=https://afferens.com
AFFERENS_POLL_INTERVAL_SECONDS=4
DEMO_MODE=false
```

Keep `DEMO_MODE=false` for product runtime. Test fixtures should be invoked only by test commands and must not be surfaced as live perception.

## Database

Start Postgres with pgvector:

```bash
docker compose up -d postgres
```

Stop it:

```bash
docker compose down
```

The default local connection shape is:

```text
postgresql://postgres:postgres@localhost:5432/afferens_memory_guardian
```

Once backend database code lands, prefer documenting the exact `DATABASE_URL` there and keeping secrets out of committed files.

## Backend

Backend files are expected under `backend/` once the backend workstream lands.

Recommended setup:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
```

Install dependencies using the file the backend workstream provides.

If `pyproject.toml` exists:

```bash
pip install -e ".[dev]"
```

If `requirements.txt` exists:

```bash
pip install -r requirements.txt
```

Expected development server shape:

```bash
uvicorn app.main:app --reload
```

Expected health checks:

```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/afferens/status
curl http://localhost:8000/api/afferens/latest
```

These endpoints must never return the API key. They should distinguish missing configuration, invalid/inactive credentials, no live events, and live events.

Expected backend test command:

```bash
python -m pytest
```

Tests may use mocked Afferens responses. Product endpoints may not use mocked responses as runtime data.

## Frontend

Frontend files are expected under `frontend/` once the frontend workstream lands.

Recommended setup:

```bash
cd frontend
npm install
npm run dev
```

Expected checks:

```bash
npm run lint
npm run build
```

The frontend should call backend APIs and must not read or store `AFFERENS_API_KEY`.

## Afferens Node Setup

1. Confirm `.env` contains an Afferens API key without printing it.
2. Confirm the Afferens account/key is active.
3. Open <https://afferens.com/node> on a phone, laptop, or USB-webcam-capable device.
4. Start the live Vision node and grant camera permissions in the browser/device UI.
5. Use `/api/afferens/status` and `/api/afferens/latest` to confirm live perception.
6. Only after the node is present should you debug camera permissions, parsing, or downstream UI behavior.

Phone, laptop webcam, and USB webcam nodes are all valid. The product should not assume a phone-only setup.

## Manual Smoke Test

Once backend and frontend exist:

1. Start Postgres.
2. Start the backend.
3. Start the frontend.
4. Open the setup/status UI.
5. Confirm the UI reports key and node state honestly.
6. Start an Afferens Node.
7. Confirm status moves from `no_live_events` to `live`.
8. Confirm the latest event view shows event metadata without exposing secrets.

Later checkpoints should add smoke tests for object memory, query answers, safety alerts, actuation attempts, and verified resolution.

## Quarantined Output

An accidental sub-agent output stash exists with the name `quarantine subagent output from wrong orchestration mode`.

Do not inspect, apply, or integrate that stash unless the user explicitly asks for salvage or review.
