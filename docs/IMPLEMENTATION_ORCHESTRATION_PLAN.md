# Afferens Memory Guardian Implementation And Orchestration Plan

## Purpose

This document is the working implementation plan for building Afferens Memory Guardian as a real, live-only product.
It also defines how the master Codex session should orchestrate isolated Codex worktree sessions, review their work, merge safely, and continue in loops until substantial checkpoints are reached.

Important orchestration rule: do not use sub-agents for implementation work. Use actual Codex app threads/sessions backed by isolated Git worktrees so each implementation lane has full project functionality, app-visible reasoning context, and isolated files.

The product requirement is strict:

- Runtime perception must be live. Do not use replayed, cached, or fixture perception data in product flows.
- Afferens is the primary physical perception layer.
- Phone, laptop webcam, or external webcam may be used as Afferens Nodes. The product must be node-agnostic.
- Backend and frontend must work end to end.
- Every answer or alert must be evidence-backed.
- The product must close the loop with verified resolution wherever possible: perceive, remember/reason, act, verify the physical state changed, and close or escalate the task.
- Safety claims must remain assistive and non-clinical.

## Source-Of-Truth Inputs

- Google Doc brief pasted into this workspace conversation.
- `Afferens_Memory_Guardian_PRD.md`.
- `docs/CODEX_ORCHESTRATION_RESEARCH.md` for Codex app worktree/thread orchestration rules.
- Official Afferens docs: `https://afferens.com/docs`.
- Official Afferens Quackathon brief: `https://afferens.com/quackathon`.
- Reference repo: `https://github.com/gamefreakoneone/Project-Memoria_Dementia-Assistant`.
- Discord clarification from the Afferens founder indicating that Afferens can be the live physical perception layer while domain-specific models handle classification/reasoning before actuation, depending on the specific project.

The pasted Google Doc brief is treated as the event/source-of-truth brief when it conflicts with other summary documents.

## Important Current State

- Git has been initialized and the planning/API-contract baseline has been pushed to `https://github.com/AbhinavGupta707/Quackathon.git`.
- The Codex app project is registered as `/Users/abhinavgupta/Desktop/Quackathon`.
- `.env` exists locally and contains the user's Afferens key. Never print, read aloud, commit, or expose it.
- `.env.example` exists and documents required environment variables.
- `.gitignore` ignores real env files.
- `.agents/` could not be created due workspace permissions; root `AGENTS.md` and `docs/AGENT_MEMORY.md` are the durable local memory files.
- An accidental sub-agent run was stopped and its output was quarantined in a Git stash named `quarantine subagent output from wrong orchestration mode`. Do not integrate that stash unless the user explicitly asks to inspect or salvage it.
- Official Codex docs state that Codex-managed worktrees are created under `$CODEX_HOME/worktrees` and normally start in detached HEAD. Detached HEAD is expected for managed worktrees and should not be diagnosed as a failure by itself.

Because Git index, branch, worktree, and commit operations can require escalated permissions in this environment, request escalation when needed.

## Product Thesis

The product should be framed as verified home assistance, not a passive camera dashboard.

Working name:

```text
Afferens Memory Guardian
```

Sharper positioning:

```text
A live home-assistance agent that perceives, remembers, acts, and verifies resolution in the physical world.
```

Judging-optimized loop:

```text
live Afferens perception
  -> evidence ledger
  -> memory / safety workflow
  -> user or caregiver action
  -> physical-state verification through Afferens
  -> task resolved, escalated, or left open with evidence
```

This matters because the hardware track rewards visible physical grounding. A product that only answers "where are my keys?" can look like a chatbot with a camera. A product that verifies "the keys were found" or "the medicine was moved to the safe zone" demonstrates a complete physical-world agent loop.

## Product Architecture

Target product architecture:

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
  - LangGraph task workflows
  - Fireworks reasoning adapter
  - query agent
  - safety rules engine
  - actuation adapter
  - verification service
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

Agent/reasoning architecture:

```text
Deterministic services
  - Afferens ingestion
  - raw event persistence
  - observation normalization
  - last-seen memory updates
  - safety rule preconditions
  - actuation logging

LangGraph workflows
  - object recovery lifecycle
  - safety alert lifecycle
  - caregiver acknowledgement lifecycle
  - verified resolution lifecycle

Fireworks AI
  - structured query routing
  - answer synthesis
  - evidence sufficiency checks
  - safety explanation wording
  - optional embeddings/reranking if selected
```

Do not make LLM availability a dependency of live ingestion. The system must ingest, persist, normalize, and expose live Afferens state even if LangGraph, Fireworks, or any other model provider is unavailable.

Optional live enrichment, only after the Afferens live path is working:

```text
Live frame source
      |
      v
Local CV Enrichment Service
  - Ultralytics YOLO tracking
  - MediaPipe pose/human presence
  - Grounding DINO / SAM 2 open-vocab localization
      |
      v
Observation enrichment records
```

Local CV must never replace Afferens as the sponsor-native physical perception source.

Third-party vision providers such as Gemini, OpenAI vision, Roboflow, or local YOLO/Grounding DINO may be used for domain-specific classification or localization if Afferens output is too coarse. If used, they must be modeled as enrichment providers and their outputs must remain traceable to a live Afferens observation or live captured frame.

## Engineering Principles

1. Diagnose in layer order:
   - Registration/discovery/install state.
   - Official activation flow.
   - Live API availability.
   - Permissions.
   - Runtime logic.

2. Build source-of-truth ledgers:
   - Raw Afferens events are immutable.
   - Normalized observations are derived and can be regenerated.
   - User-facing answers cite observations, not vague memory.

3. Prefer explicit interfaces:
   - Afferens adapter.
   - Perception normalizer.
   - Memory service.
   - Safety service.
   - Actuation service.
   - Query service.

4. Make live state honest:
   - If no live node is connected, say so.
   - If the key is invalid, say so without exposing it.
   - If an object is not currently visible, do not imply it is visible.

5. Keep safety conservative:
   - Use "possible", "appears", "needs human verification".
   - Do not claim diagnosis, emergency response, fall-detection certification, or medical monitoring.

6. Keep parallel work conflict-free:
   - Each Codex worktree session owns a narrow file/domain surface.
   - Parallel worktree sessions must not edit the same files unless explicitly coordinated.
   - The master session owns merges, conflict resolution, and final integration.

7. Separate evidence from interpretation:
   - Afferens and raw events establish physical evidence.
   - Fireworks and other LLM/VLM providers interpret, classify, explain, or enrich.
   - User-facing flows must show which evidence and which inference produced an answer or alert.

8. Prefer verified resolution over one-way alerts:
   - An alert is not done when a message is sent.
   - A recovery task is not done when an answer is generated.
   - Whenever possible, a live Afferens observation must verify the physical state has changed.

## Blue-Sky Stack

### Backend

- Python 3.11+.
- FastAPI.
- Pydantic v2.
- SQLAlchemy 2 or SQLModel.
- Alembic migrations.
- HTTPX for Afferens calls.
- Pytest with mocked Afferens responses for tests only.
- Uvicorn.
- LangGraph for stateful task workflows from Checkpoint 2 onward.
- Fireworks AI as the primary LLM/structured-output provider for reasoning and explanation.

### Database

- Postgres as the primary durable store.
- `pgvector` for semantic memory in the same transactional database.
- Avoid SQLite for the main product because this should be production-shaped.

### Frontend

- Next.js + TypeScript.
- TanStack Query or equivalent for server state.
- SSE or WebSocket for live updates.
- Accessible, high-contrast operational UI.

### Optional Workers

- Redis is recommended if LangGraph/LangSmith deployment or asynchronous task workflows require it.
- Redis Queue, Arq, or Celery may be added if background processing becomes necessary.
- Do not add independent worker complexity until synchronous ingestion and query flows are working.

### Agent And Model Providers

- LangGraph is part of the target stack, but not the dependency for Checkpoint 1's Afferens spine.
- Fireworks AI is the default reasoning provider for structured LLM calls.
- Provider adapters must be explicit so Fireworks can be swapped or supplemented without changing business logic.
- Vision-capable external providers are optional and should be privacy-gated.

### Optional CV

- Ultralytics YOLO tracking for common objects/persons.
- MediaPipe Pose for human presence/posture signals.
- Grounding DINO + SAM 2 for open-vocabulary object localization.

Optional CV is a later checkpoint, not part of the first critical path.

## Core Backend Modules

```text
backend/
  app/
    main.py
    config.py
    db.py
    models.py
    schemas.py
    afferens_adapter.py
    observations.py
    normalizer.py
    memory.py
    workflows/
      graph.py
      object_recovery.py
      safety_alert.py
      verified_resolution.py
    llm/
      fireworks_adapter.py
      schemas.py
    query_agent.py
    safety.py
    actuation.py
    verification.py
    realtime.py
  tests/
    test_afferens_adapter.py
    test_normalizer.py
    test_memory.py
    test_query_agent.py
    test_safety.py
```

## Core Frontend Modules

```text
frontend/
  app/
    setup/
    dashboard/
    ask/
    caregiver/
    evidence/[id]/
  components/
    LiveStatusPanel.tsx
    RawAfferensPanel.tsx
    ObjectMemoryTable.tsx
    AskInterface.tsx
    ActiveTaskConsole.tsx
    AlertQueue.tsx
    EvidenceTimeline.tsx
    NodeSetupChecklist.tsx
  lib/
    api.ts
    realtime.ts
    types.ts
```

## Data Model

Minimum production-shaped tables:

- `afferens_raw_events`
- `observations`
- `detected_objects`
- `last_seen_objects`
- `alerts`
- `queries`
- `tasks`
- `task_events`
- `actuation_attempts`
- `verification_checks`
- `system_status_events`

Recommended relationships:

```text
afferens_raw_events.id
  -> observations.raw_event_id
  -> detected_objects.observation_id
  -> alerts.observation_id
  -> queries.evidence_observation_ids
  -> tasks.evidence_observation_ids
  -> verification_checks.observation_id
  -> actuation_attempts.alert_id
```

Task lifecycle states:

```text
open
waiting_for_human
actuation_attempted
verification_pending
verified_resolved
escalated
dismissed
failed_verification
```

## API Contract

Minimum API:

```text
GET  /api/health
GET  /api/afferens/status
GET  /api/afferens/latest
POST /api/perception/sync
GET  /api/observations/latest
GET  /api/objects/last-seen
POST /api/query
GET  /api/alerts
POST /api/alerts/{alert_id}/ack
POST /api/actuate/alarm
GET  /api/tasks
POST /api/tasks/{task_id}/verify
POST /api/tasks/{task_id}/resolve
GET  /api/events/stream
```

Status semantics:

- Missing key: `configured=false`, no secret details.
- Invalid key: show `401` state.
- Inactive key: show `403` state.
- No node/events: show `404` or `no_live_events`.
- Live event available: show timestamp, source node, modality, and event ID.

## Primary Product Loops

### Loop 1: Object Recovery

```text
live observation sees object
  -> update last-seen memory
  -> user asks where object is
  -> LangGraph retrieves current observation and memory
  -> Fireworks generates evidence-backed answer
  -> user finds object and places it in view or confirms recovery
  -> Afferens verification check confirms object is visible or task is manually confirmed
  -> task state becomes verified_resolved or waiting_for_human
```

### Loop 2: Medicine Safety

```text
live observation sees medicine in unsafe zone
  -> deterministic safety rule opens task
  -> Fireworks drafts conservative alert explanation
  -> UI/browser alarm/caregiver alert triggers
  -> human moves medicine to safe zone or removes it from view
  -> Afferens verification check confirms safe-zone state or no-longer-visible state
  -> task state becomes verified_resolved or escalated
```

### Loop 3: Cooking Risk

```text
live observation sees pan/stove marker and no person visible
  -> deterministic safety rule opens task
  -> alert and actuation attempt
  -> human returns or clears stove marker
  -> Afferens verification check confirms changed state
  -> task state becomes verified_resolved or remains open
```

## Checkpoints

### Checkpoint 1: Live Afferens Spine

Goal: prove the product has a real live perception backbone.

Acceptance criteria:

- Git repo initialized and baseline committed.
- Backend scaffold exists.
- Frontend scaffold exists.
- Postgres/pgvector runs via Docker Compose or equivalent.
- Backend reads `.env` without exposing secrets.
- `/api/health` works.
- `/api/afferens/status` maps missing/invalid/inactive/no-node/live states.
- `/api/afferens/latest` attempts real Afferens perception.
- Frontend setup/status page shows Afferens configuration and node state honestly.
- No runtime cached perception paths exist.
- API contracts reserve task/workflow fields, but Checkpoint 1 does not depend on LangGraph or Fireworks being available.

Manual testing likely required:

- User may need to start an Afferens Node on phone or laptop webcam to move from `no_live_events` to `live`.
- Browser or Chrome extension may be used to operate Afferens onboarding pages and node setup, with user handling sign-in, camera permission, and secrets.

### Checkpoint 2: Evidence-Backed Memory Product

Goal: turn live perception into durable, queryable object memory and begin verified task workflows.

Acceptance criteria:

- Raw Afferens events are persisted immutably.
- Raw events are normalized into internal observations.
- Detected objects are extracted and stored.
- `last_seen_objects` updates from real observations.
- `/api/perception/sync` fetches, stores, normalizes, and updates memory from live Afferens data.
- `/api/objects/last-seen` returns current object memory.
- `/api/query` answers object-location questions with evidence IDs and timestamps.
- LangGraph object-recovery workflow exists.
- Fireworks adapter exists for structured query routing, evidence sufficiency, and answer synthesis.
- Tasks can be opened from object recovery questions and verified/resolved from a later live observation or explicit human confirmation.
- Frontend dashboard shows latest raw event, normalized observation, and object memory.
- Ask page supports "Where are my keys?" style queries.
- Active task console shows object recovery tasks and verification state.
- Tests cover normalizer, memory update, and query routing.

Manual testing likely required:

- Put real objects in view.
- Sync perception.
- Move/remove an object.
- Ask where the object is.
- Confirm the app distinguishes current visibility from last-seen memory.
- Put the recovered object back into view and confirm the task can become `verified_resolved`.

### Checkpoint 3: Safety, Actuation, And Product Hardening

Goal: complete the product loop from live perception to action, verification, and operational UX.

Acceptance criteria:

- Safety rules create alerts from live observations.
- Sensor offline/no-event state is represented honestly.
- Caregiver alert UI lists, opens, and acknowledges alerts.
- Browser/dashboard alarm works.
- Afferens actuation adapter attempts `/api/actuation` and logs success/failure.
- Verification checks can close or escalate safety tasks based on a later live Afferens observation.
- Evidence inspector links answers and alerts back to raw/normalized observations.
- Frontend receives live updates via SSE/WebSocket or a robust polling loop.
- README explains setup, architecture, Afferens integration, and safety boundaries.
- Tests cover safety rules, actuation logging, and alert acknowledgement.
- No product runtime path relies on fixtures or cached perception.

Manual testing likely required:

- Stage safety object or hazard marker in view.
- Trigger perception sync.
- Confirm alert and actuation.
- Change the physical scene and verify the alert resolves or remains open based on evidence.
- Acknowledge alert.
- Verify evidence trail.

### Optional Checkpoint 4: Live CV Enrichment

Goal: improve object localization and human-presence quality without undermining Afferens primacy.

Acceptance criteria:

- Local CV enrichment is live-only.
- Enrichment records are clearly marked as non-Afferens.
- Afferens event remains the primary evidence anchor.
- YOLO/MediaPipe/Grounding DINO integration can be disabled without breaking core product.
- UI distinguishes Afferens perception from local enrichment.

This checkpoint should only start after Checkpoint 3 unless Afferens labels are too coarse to make Checkpoint 2 possible.

## Master Orchestrator Loop

The current session acts as master orchestrator. It should work in loops:

1. Inspect current project state.
2. Decide the next checkpoint target.
3. Identify independent workstreams that can run safely in parallel.
4. Create only substantial Codex worktree sessions.
5. Give each session a clear title and record its thread ID, `codex://threads/<thread-id>` link, worktree path, logical lane, ownership, and status.
6. Assign each session explicit file ownership.
7. Monitor progress about every five minutes through app thread tools and user-visible thread links.
8. Review each completed session's diff, tests, and notes.
9. Merge in a controlled order.
10. Run integration tests and fix integration issues.
11. Decide whether to continue to the next checkpoint or stop for manual testing.

Do not create worktree sessions for tiny tasks that are cheaper and safer for the master session to do directly.
Do not use sub-agents for implementation work.

## Worktree Session Creation Rules

Use actual Codex threads/sessions with isolated Git worktrees. Prefer the Codex app thread tools (`list_projects`, then `create_thread` with `environment.type = "worktree"`) over sub-agent tooling.

Codex app-managed worktree threads are the default for this project because they are visible, searchable, and monitorable inside the Codex app. Manual project-local `.worktrees/...` checkouts are allowed only as an explicit fallback when branch/location control matters more than native app visibility; see `docs/CODEX_ORCHESTRATION_RESEARCH.md`.

The master session should:

1. Create a new Codex thread for each substantial lane.
2. Target the saved Quackathon project.
3. Use a worktree environment.
4. Start each managed worktree from current `main` unless there is a deliberate reason to use another existing base ref.
5. Before passing `startingState.branchName`, verify it with `git rev-parse --verify <branch>`.
6. Do not pass a desired new lane branch as `startingState.branchName`. The Codex app treats that field as an existing starting ref.
7. Expect the created worktree to be detached HEAD at the selected base commit. This is normal for Codex-managed worktrees.
8. Keep lane names as logical ownership labels in the prompt and thread title until a branch is needed for commit, push, or PR.
9. If the work should stay in the worktree and be pushed, create a branch at commit time using the Codex app's Create branch here flow or a unique explicit branch inside that worktree.
10. If the work should move into the foreground checkout, use Handoff instead of checking out the same branch in multiple worktrees.
11. After thread creation, verify the thread appears in `list_threads` and the worktree appears in `git worktree list --porcelain`.
12. Immediately set a concise title and share/record a `codex://threads/<thread-id>` link.
13. Do not rely on pinning for visibility. Pin only when the user wants it or when a long-running important worktree needs cleanup protection.
14. Keep a local table of thread IDs, titles, worktree paths, logical lanes, ownership, and status.

Failure mode to avoid:

- Codex app worktree creation currently treats `startingState.branchName` as an existing Git reference. It does not create a new branch from that string.
- Passing a non-existent lane such as `ws/c1-frontend-shell` causes `git worktree add` to fail with `fatal: invalid reference`.
- A successful managed worktree creation normally leaves the checkout detached at the selected commit. That is workable and expected. Create a branch only when the work needs to be committed/pushed from that worktree.
- Failed pending worktree cards in the app sidebar may not appear as normal completed thread records. Diagnose them as failed creation attempts unless `list_threads` shows a live thread.
- Diagnose this class of failure in layer order: check local refs and worktree registration first, then permissions or runtime issues.

Naming convention:

```text
logical lanes:
  c1-backend-spine
  c1-frontend-shell
  c1-docs-devex

branches:
  ws/c1-backend-spine
  ws/c1-frontend-shell
  ws/c1-docs-devex
```

Branch names are created only when needed for commits, pushes, or PRs. They are not passed as new worktree starting refs unless they already exist.

Visibility protocol:

- After `create_thread`, call `list_threads` and confirm the returned thread ID, title, status, and `cwd`.
- Use `set_thread_title` to make the lane obvious in the sidebar and thread search.
- Use `set_thread_pinned` only when the user wants pinned visibility or when an important long-running worktree needs cleanup protection.
- Report the deep link `codex://threads/<thread-id>` to the user for each active spawned session.
- Tell the user to use thread search (`Cmd+G` on macOS) for the title, branch/lane label, or thread ID if a worktree thread is not visible in the current project list.
- If only a failed pending worktree card exists and no thread ID is returned by `list_threads`, do not assume there is hidden work. Fix the starting ref or setup error and create a fresh visible thread.
- Treat the app sidebar as a convenience view, not the source of truth. A thread is real when it has a thread ID in `list_threads`, opens by `codex://threads/<thread-id>`, and has the expected Git worktree registration.

Each worktree session prompt must include:

- Repository/context.
- Workstream name.
- First-read source files.
- Goal.
- Checkpoint target.
- Owned files/directories.
- Explicit files/directories not to edit.
- Requirements and product constraints.
- Verification commands/tests.
- Commit and clean-worktree expectation.
- Required final handoff format.
- No-secrets rule.
- Live-only runtime rule.
- Explicit instruction that it is an isolated worktree session, not a sub-agent.

Default reasoning:

- Use high reasoning for normal implementation sessions.
- Use extra-high reasoning for architecture, data-model, merge conflict resolution, live Afferens debugging, and security/safety review.

Browser/Chrome/computer-use permissions:

- Allowed when needed for onboarding, Afferens docs, local end-to-end testing, or visual QA.
- User must handle sign-in, secrets, OAuth, camera permission, and any CAPTCHA.
- Do not inspect browser cookies, local storage, password stores, or secrets.

## Parallelization Matrix

### Safe To Run In Parallel As Worktree Sessions

- Backend scaffold and Afferens adapter.
- Frontend shell and setup/status UI.
- Product docs and README.
- Database models and migration draft, if file ownership is coordinated.
- Query UI after API schemas are stable.
- Caregiver UI after alert schemas are stable.

### Do Not Run In Parallel Without Coordination

- Multiple sessions editing `docker-compose.yml`.
- Multiple sessions editing root package/workspace config.
- Multiple sessions editing database models and migrations.
- Multiple sessions changing shared API schemas.
- Frontend and backend changing endpoint names independently.

### Master-Owned Files During Merges

- `docker-compose.yml`
- root README
- root env examples
- shared API schema docs
- migration squashing/ordering
- final integration fixes

## Proposed Workstream Batches

### Batch 1: Reach Checkpoint 1

Worktree Session A: Backend Spine

- Owns `backend/**`.
- Build FastAPI app, config, health endpoint, Afferens adapter, status/latest endpoints, tests.
- Include placeholder provider interfaces for later LangGraph/Fireworks integration, but do not implement workflow logic in Checkpoint 1.
- Must not touch frontend.

Worktree Session B: Frontend Shell

- Owns `frontend/**`.
- Build Next.js app shell, setup/status page, API client types against documented contract.
- Must not touch backend except reading API contract.

Worktree Session C: DevEx And Docs

- Owns `README.md`, `docs/**`, Docker Compose draft, architecture docs.
- Coordinates with master before finalizing `docker-compose.yml`.

Master:

- Initializes Git.
- Creates Codex worktree sessions.
- Writes/locks API contract.
- Merges in order: backend, frontend, docs/devex.
- Runs integrated app and status endpoint.

### Batch 2: Reach Checkpoint 2

Status after second Batch 2 execution pass:

- Completed and merged: Data And Memory backend lane.
- Completed and merged: Dashboard, Ask UI, And Active Tasks frontend lane.
- Completed and merged: Backend Query Workflow lane with `/api/query`, Fireworks adapter, LangGraph object-recovery workflow wrapper, task verification/resolution, alert list/ack endpoints, and Alembic migration.
- Completed and merged: Runtime docs/devex lane, then master reconciliation after backend query workflow landed.
- Completed and merged: Frontend Resolution Integration lane with task verify, human resolve, and alert acknowledgement controls.
- Checkpoint 2 is code-complete on `main`.
- Still required before calling the product live-validated: integrated live smoke testing with local Postgres, backend, frontend, Fireworks config if available, and a live Afferens node.

Completed Worktree Session A: Data And Memory

- Owns backend models, migrations, raw event ledger, observation persistence, object memory service, task tables, verification-check tables.
- Landed on `main` through `ws/c2-backend-data-memory`.
- Added `/api/perception/sync`, `/api/observations/latest`, `/api/objects/last-seen`, `/api/tasks`, durable model scaffolding, normalizer, service/repository boundaries, and tests.

Completed Worktree Session B: Query And Workflows

- Owns query routing, object aliasing beyond simple normalized labels, LangGraph object-recovery workflow, Fireworks adapter, `/api/query`, task verification/resolution endpoints, and query/workflow tests.
- Landed on `main` through `ws/c2-backend-query-workflow`.
- Added deterministic object search, Fireworks structured adapter, LangGraph workflow wrapper with fallback, evidence-backed query answers, live Afferens task verification, human resolution, alert list/ack routes, repository/service methods, focused tests, and durable schema migration.

Completed Worktree Session C: Dashboard, Ask UI, And Active Tasks

- Owns dashboard, object memory table, raw event panel, ask interface, active task console.
- Landed on `main` through `ws/c2-frontend-memory-query`.
- Added evidence-aware memory console UX and honest unavailable states for not-yet-implemented endpoints.

Completed Worktree Session D: Frontend Resolution Integration

- Owns `frontend/**` only.
- Landed on `main` through `ws/c2-frontend-resolution-integration`.
- Wired task verify, task resolve, and alert acknowledge controls to the implemented backend endpoints.
- Refreshes tasks/alerts after each action and keeps honest loading/error states.
- Checks passed in lane: `npm run lint`, `npm run typecheck`, and `npm run build`.

Master:

- Integrated memory sync, query, task verification/resolution, and alert acknowledgement.
- Ran full integrated checks after the final Checkpoint 2 merge: backend tests, backend compile, frontend lint, frontend typecheck, frontend build, and whitespace diff check.
- Still must run live Afferens sync/query/verify/ack smoke test once local keys and node are available.
- Resolves any schema/API mismatches found during live smoke before proceeding deeply into Checkpoint 3.

### Batch 3: Reach Checkpoint 3

Worktree Session A: Safety And Actuation

- Owns safety rules, alerts, actuation adapter, safety LangGraph workflow, verification checks, tests.

Worktree Session B: Caregiver And Evidence UI

- Owns caregiver page, alert acknowledgement UI, evidence inspector.

Worktree Session C: Hardening And QA

- Owns tests, README updates, local run docs, safety boundary docs.
- Does not change core runtime logic without approval.

Master:

- Integrates full loop.
- Runs tests.
- Performs local browser QA.
- Stops for manual hardware/camera testing.

## Merge And Review Procedure

For each completed worktree session:

1. Inspect summary and changed files.
2. Run targeted tests for that workstream.
3. Review for:
   - secret exposure
   - cached runtime perception
   - API contract drift
   - unsafe safety claims
   - missing evidence trail
   - broad/unnecessary abstractions
4. Merge only after review.
5. Run integration tests after each merge or after a compatible pair of merges.
6. Keep a short merge note in `docs/AGENT_MEMORY.md`.

If two sessions conflict, the master resolves conflict manually and reruns the relevant tests.

## Required Completion Report For Worktree Sessions

Every worktree session must end with:

```text
Status: complete | blocked
Thread ID:
Thread link:
Logical lane:
Branch/worktree:
Files changed:
Commands run:
Tests run:
Manual checks:
Known risks:
Integration notes:
Next recommended step:
```

## Commands To Prefer

Use these commands as appropriate:

```bash
rg --files
rg "pattern"
python -m pytest
npm run lint
npm run build
docker compose up --build
docker compose down
```

Networked package installs or remote API probes may require escalation.

## Pushbacks And Decisions

1. Do not start with local CV.
   Afferens live integration is the product's spine and the sponsor requirement. Local CV is useful only after live Afferens works or if Afferens labels are insufficient.

2. Use LangGraph deliberately.
   LangGraph is a first-class target dependency for stateful object-recovery, safety-alert, caregiver, and verified-resolution workflows. It should start in Checkpoint 2. Checkpoint 1 remains deterministic so live Afferens ingestion can be debugged without agent/runtime uncertainty.

3. Use Fireworks as the primary reasoning provider.
   Fireworks should handle structured query routing, evidence sufficiency checks, answer synthesis, and safety explanation. It must reason over structured observations by default. Raw frame/image upload to Fireworks or another VLM should be opt-in and privacy-gated.

4. Do not use SQLite for the main implementation.
   SQLite is fine for a demo, but the user's requirement is a proper product. Use Postgres + pgvector.

5. Do not make the phone mandatory.
   The product should support any Afferens Vision node. The setup UI should explain phone and laptop webcam options.

6. Do not hide no-node state.
   If no camera/node has been activated, the product should say that honestly and still allow setup/status workflows.

7. Do not present Afferens as a checkbox.
   Afferens should be the live physical evidence gate. Domain-specific models may enrich classification and reasoning, but user-facing task states should remain grounded in live Afferens observations.

## Immediate Next Step

After this plan is accepted:

1. Initialize Git.
2. Commit the planning baseline.
3. Use `list_projects` to find the Quackathon project ID.
4. Create Checkpoint 1 Codex worktree threads for backend spine, frontend shell, and docs/devex only if each can own non-overlapping files.
5. Track each thread ID and branch/worktree assignment locally.
