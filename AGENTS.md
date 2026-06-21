# AGENTS.md

## Core Instruction

Diagnose in layer order, not by symptom: if a feature is "missing", "unavailable", or not listed, first check registration/discovery/install state and official activation flows; only debug permissions/runtime after the feature is actually present.

## Project-Specific Instructions

This repository is for Afferens Memory Guardian, a live physical-perception product.

Follow `docs/IMPLEMENTATION_ORCHESTRATION_PLAN.md` and `docs/AGENT_MEMORY.md`.

## Live-Only Runtime Rule

Do not implement runtime product flows that depend on cached, replayed, or fixture perception data.

Fixtures are allowed only for tests.

If no live Afferens Node is active, the product must show an honest no-live-node state.

Prefer verified resolution over one-way alerts. Wherever possible, a task should move through live perception, reasoning, action, later live verification, and then resolution or escalation.

## Secrets

Never print, inspect, expose, commit, or transmit `.env` contents or `AFFERENS_API_KEY`.

Use `.env.example` for documented configuration.

## Afferens Integration

Afferens is the primary perception source.

Use official activation/discovery flows first:

1. Confirm API key configuration without revealing the key.
2. Confirm Afferens account/key status.
3. Confirm node setup at `https://afferens.com/node`.
4. Confirm live `/api/perception` availability.
5. Only then debug camera permissions, runtime parsing, or downstream product logic.

Phone, laptop webcam, and USB webcam are all valid Afferens Node options. Do not hard-code product assumptions that require a phone.

Domain-specific AI providers may enrich classification or reasoning, but Afferens must remain the live physical evidence gate.

## LangGraph And Fireworks

Use LangGraph as the workflow layer for stateful object-recovery, safety-alert, caregiver-acknowledgement, and verified-resolution flows starting Checkpoint 2.

Use Fireworks AI as the primary LLM/structured-output provider for query routing, evidence sufficiency checks, answer synthesis, and safety explanation.

Do not make Checkpoint 1's live Afferens ingestion depend on LangGraph or Fireworks availability.

## Safety Claims

Use conservative language:

- possible
- appears
- may need checking
- human verification required

Do not claim medical-device behavior, diagnosis, emergency response, certified fall detection, or autonomous monitoring.

## Orchestration

The master session owns orchestration, Codex worktree thread creation, monitoring, review, merges, and integration fixes.

Do not use sub-agents for implementation work. Use actual Codex threads/sessions backed by isolated Git worktrees.

Worktree sessions must do substantial work with clear ownership. Do not create worktree sessions for trivial edits.

When parallelizing:

- Use separate Codex worktree sessions, not sub-agents.
- Native Codex-managed worktrees normally start in detached HEAD. This is expected and should not be treated as a failure.
- Use `startingState.branchName` only for an existing base ref, normally `main`. It is a starting point, not a create-new-branch instruction.
- Keep lane names as logical ownership labels in the thread title/prompt until a branch is actually needed for commit/push/PR.
- Create a real Git branch only at commit/handoff time, either with the Codex app's Create branch here flow or an explicit unique branch inside that worktree.
- After creation, verify app registration with `list_threads` and Git registration with `git worktree list --porcelain`.
- Immediately set a clear thread title, pin active worktree threads, and share/record the `codex://threads/<thread-id>` link so the user can open each session in the Codex app.
- Assign non-overlapping files.
- Avoid concurrent edits to shared schemas, migrations, root config, or Docker Compose unless coordinated.
- Require each session to report files changed, commands run, tests run, risks, and integration notes.

An accidental sub-agent run was quarantined in a Git stash. Do not integrate sub-agent output unless the user explicitly requests inspection or salvage.

## Preferred Build Order

1. Git baseline.
2. Backend and frontend scaffolds.
3. Postgres/pgvector.
4. Afferens status/latest endpoints.
5. Raw event ledger.
6. Observation normalization.
7. Object memory.
8. LangGraph/Fireworks query workflow and active tasks.
9. Query UI and dashboard.
10. Safety, actuation, and verification.
11. Caregiver/evidence UI.
12. Hardening and tests.
