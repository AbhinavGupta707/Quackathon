# Agent Memory

## Project

Afferens Memory Guardian is a live physical-perception product for the Quackathon Hardware / Physical Perception track.

The product watches a real scene through an Afferens Vision Node, stores evidence-backed object memories, answers object-location questions, creates caregiver-facing alerts for possible staged risks, and verifies when physical-world tasks are resolved.

## Non-Negotiables

- Runtime perception must be live.
- Do not use cached, replayed, or fixture perception in product flows.
- Fixtures are allowed only in tests.
- Afferens is the primary perception source.
- Phone, laptop webcam, and external webcam should all be treated as possible Afferens Nodes.
- Never print or expose `.env` or `AFFERENS_API_KEY`.
- Every answer or alert must cite evidence.
- Prefer verified resolution over one-way alerts: perceive, remember/reason, act, verify the physical state changed, and close/escalate the task.
- Safety claims must be conservative and non-clinical.
- LangGraph is a first-class workflow layer starting Checkpoint 2.
- Fireworks AI is the primary reasoning/structured-output provider.

## Orchestration Model

This project should be built by a master orchestrator session using actual Codex worktree threads/sessions.

Do not use sub-agents for implementation work. Worktree sessions have better project functionality, branch isolation, and durable reasoning context for this project.

Read `docs/CODEX_ORCHESTRATION_RESEARCH.md` before spawning or diagnosing worktree sessions.

The master session:

- Plans the next checkpoint.
- Creates isolated Codex worktree sessions only for substantial work.
- Uses `startingState.branchName` only for an existing base ref, normally `main`. `branchName` is a starting reference, not a create-new-branch instruction.
- Treats native Codex-managed detached HEAD worktrees as expected. Do not force branch checkout at the start of worktree sessions.
- Keeps lane names as logical ownership labels in the thread title and prompt until a branch is needed for commit/push/PR.
- Creates a real branch only at commit/handoff time, either with the Codex app's Create branch here flow or an explicit unique branch inside that worktree.
- Checks app registration with `list_threads` and Git registration with `git worktree list --porcelain` after creation.
- Immediately sets a clear title, records thread IDs, and shares `codex://threads/<thread-id>` links so the user can monitor sessions in the Codex app.
- Does not rely on pinning for visibility. Pin only when the user wants it or when a long-running important worktree needs cleanup protection.
- Assigns non-overlapping file ownership.
- Monitors progress.
- Reviews diffs and tests.
- Merges carefully.
- Runs integration checks.
- Stops at manual-testing checkpoints when hardware/camera access is required.

Default spawned-session reasoning should be high. Use extra-high reasoning for architecture, merge conflicts, live Afferens debugging, and safety/security review.

## Checkpoints

Checkpoint 1: Live Afferens Spine

- Backend, frontend, Postgres/pgvector, health endpoint, Afferens status/latest endpoints, setup/status UI.

Checkpoint 2: Evidence-Backed Memory Product And Object Recovery

- Raw event ledger, normalization, object memory, object-location query, LangGraph object-recovery workflow, Fireworks reasoning adapter, dashboard, ask UI, active task console.

Checkpoint 3: Safety, Actuation, And Product Hardening

- Safety rules, alerts, actuation logging, verified safety resolution, caregiver UI, evidence inspector, README, tests.

Optional Checkpoint 4: Live CV Enrichment

- YOLO/MediaPipe/Grounding DINO/SAM 2 live enrichment only after Afferens spine works.

## Current State Notes

- `.env` exists locally with the user's Afferens key. Treat it as secret.
- `.env.example` exists.
- `.gitignore` ignores env files.
- Git is initialized and connected to `https://github.com/AbhinavGupta707/Quackathon.git`.
- `.agents/` could not be created due workspace permissions, so this file and root `AGENTS.md` are the local memory surface.
- An accidental sub-agent run was stopped. Its unmerged output is quarantined in a Git stash named `quarantine subagent output from wrong orchestration mode`; do not integrate it unless the user explicitly asks.

## Completed Orchestration

Checkpoint 2 batch 1 ran from `main` using Codex app-managed worktree threads.

| Lane | Thread ID | Link | Worktree | Ownership |
| --- | --- | --- | --- | --- |
| C2 Backend Data Memory | `019eeb13-fd88-76e0-a3af-da4ef15258b3` | `codex://threads/019eeb13-fd88-76e0-a3af-da4ef15258b3` | `/Users/abhinavgupta/.codex/worktrees/46a3/Quackathon` | `backend/**` only |
| C2 Frontend Memory Query | `019eeb14-44e7-7452-9d5d-d5653b359dd6` | `codex://threads/019eeb14-44e7-7452-9d5d-d5653b359dd6` | `/Users/abhinavgupta/.codex/worktrees/8594/Quackathon` | `frontend/**` only |

These sessions were full Codex app worktree sessions, not sub-agents. They were created from existing `main`, ran as Codex-managed detached HEAD worktrees, then were committed to scoped branches at handoff.

Merged results on `main`:

- `5350f0b` merged `ws/c2-backend-data-memory`.
- `0a2f2ea` merged `ws/c2-frontend-memory-query`.
- Backend now has SQLAlchemy/Alembic-ready durable models, lazy DB status/session setup, raw-event persistence, observation normalization, object memory updates, task/alert creation seams, `/api/perception/sync`, `/api/observations/latest`, `/api/objects/last-seen`, and `/api/tasks`.
- Frontend now has a dense live memory console with sync feedback, latest observation/evidence display, object memory table, ask UI evidence states, active task console, and honest unavailable states.
- Integrated checks after merge: backend `python3 -m pytest` passed with 21 tests; frontend `npm run lint` passed; frontend `npm run build` passed.

Checkpoint 2 batch 2 backend/docs pass:

- Merged backend query workflow through `ws/c2-backend-query-workflow`.
- Backend now has `/api/query`, Fireworks structured reasoning adapter, LangGraph object-recovery workflow wrapper with deterministic fallback, `/api/tasks/{task_id}/verify`, `/api/tasks/{task_id}/resolve`, `/api/alerts`, `/api/alerts/{alert_id}/ack`, and a real Alembic durable schema migration.
- Query answers must remain evidence-backed: current live observation first, durable memory second, no invented locations.
- Task verification must fetch fresh live Afferens data and sync through the normalizer before deciding verified/not_verified/inconclusive.
- Merged runtime docs through `ws/c2-devex-runtime-docs`, then reconciled docs with the implemented backend endpoints.

Remaining Checkpoint 2 gaps:

- Frontend task verify/resolve controls and alert acknowledgement are wired on `main` through `ws/c2-frontend-resolution-integration`.
- Full local live Afferens plus Fireworks smoke test has not been run.

Next recommended worktree batch:

- Integrated main checks after merge: backend tests, backend compile, frontend lint, frontend typecheck/build.
- Manual checkpoint after that: run local DB migration, start backend/frontend, connect live Afferens node, sync/query/verify/ack with real API keys.
