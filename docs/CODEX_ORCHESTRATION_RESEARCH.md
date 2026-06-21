# Codex App Orchestration Research

## Purpose

This note records the current, official-doc-backed orchestration model for this project.
It exists because the project intentionally uses visible Codex app worktree threads, not sub-agents, and because earlier worktree creation attempts failed from an incorrect branch-start assumption.

## Official Codex Findings

Sources checked on 2026-06-21:

- Official Codex manual via `https://developers.openai.com/codex/codex-manual.md`.
- Codex app features: `https://developers.openai.com/codex/app/features`.
- Codex app commands and deep links: `https://developers.openai.com/codex/app/commands`.
- Codex app worktrees: `https://developers.openai.com/codex/app/worktrees`.
- Codex subagents: `https://developers.openai.com/codex/subagents`.

Relevant findings:

- The Codex app is designed for parallel desktop threads and has built-in worktree support.
- Creating a separate background thread should be explicit.
- Worktree threads are local Codex app threads backed by Git worktrees, not sub-agents.
- Codex-managed worktrees are created under `$CODEX_HOME/worktrees`.
- A managed worktree normally starts in detached HEAD at the selected branch's HEAD commit.
- Detached HEAD is expected and should not be treated as a failed worktree setup.
- A branch can be checked out in only one Git worktree at a time.
- If staying in a worktree and pushing work, create a branch from that worktree when needed.
- If bringing work into the foreground checkout, use the Codex app Handoff flow.
- The app supports thread search with `Cmd+G` on macOS.
- The app supports deep links in the form `codex://threads/<thread-id>`.
- Subagents are a different Codex feature. They are useful for delegated internal analysis, but are not the requested orchestration mechanism for this project.

## Diagnosis Of The Failed Worktree Cards

The red "Worktree init failed" cards were caused by trying to create Codex app worktrees from lane branch names that did not exist yet, for example:

```text
fatal: invalid reference: ws/c1-frontend-shell
```

Layer-order diagnosis:

1. Registration/discovery: the desired lane branch did not exist as a Git ref.
2. Official activation flow: Codex app `startingState.branchName` expects an existing starting branch/ref.
3. Runtime/permissions: not the first failure layer in this case.

Those failed cards should be treated as failed setup attempts unless `list_threads` shows a live thread ID behind them.

## Current Completed Worktree Threads

The Checkpoint 1 work already completed through real Codex app worktree threads. They are not sub-agents.

| Lane | Thread ID | Deep link | Worktree |
| --- | --- | --- | --- |
| Backend spine | `019eeaed-320d-7773-a68b-9a2ef00dc4ac` | `codex://threads/019eeaed-320d-7773-a68b-9a2ef00dc4ac` | `/Users/abhinavgupta/.codex/worktrees/0c2b/Quackathon` |
| Frontend shell | `019eeaf2-0014-7202-bbc1-1031302204de` | `codex://threads/019eeaf2-0014-7202-bbc1-1031302204de` | `/Users/abhinavgupta/.codex/worktrees/4a36/Quackathon` |
| Docs DevEx | `019eeaf2-37a1-7a82-808a-8e0444861ad3` | `codex://threads/019eeaf2-37a1-7a82-808a-8e0444861ad3` | `/Users/abhinavgupta/.codex/worktrees/c36c/Quackathon` |

These threads were renamed with a `Quackathon C1` prefix and pinned after the visibility diagnosis so the user can find them more easily in the app. Pinning was a visibility aid, not proof that they were real threads.

## Correct Future Spawn Protocol

For future batches:

1. Use `list_projects` and target `/Users/abhinavgupta/Desktop/Quackathon`.
2. Use `create_thread` with `environment.type = "worktree"`.
3. Use `startingState.branchName = "main"` unless there is a deliberate reason to start from another existing branch.
4. Do not pass a desired new lane branch as `startingState.branchName`.
5. Treat detached HEAD as normal for native Codex-managed worktrees.
6. Put the logical lane in the title and prompt, for example `Quackathon C2 Data Memory`.
7. Immediately call `set_thread_title`.
8. Confirm the thread with `list_threads` and record its ID, title, status, and cwd.
9. Confirm Git worktree registration with `git worktree list --porcelain`.
10. Report the `codex://threads/<thread-id>` link to the user.
11. Do not rely on pinning for visibility. Pin only when the user wants it or when an important long-running worktree needs cleanup protection.
12. Monitor the visible thread with `read_thread` or by opening the app thread.
13. Create a Git branch only when the work needs to be committed or pushed from the worktree.
14. Use Handoff if the work should be brought back into the foreground checkout.

## App-Managed Versus Manual Worktrees

There are two valid isolated-worktree orchestration patterns:

| Pattern | Worktree location | Visibility | Best use |
| --- | --- | --- | --- |
| Codex app-managed worktree thread | `$CODEX_HOME/worktrees/...` such as `/Users/abhinavgupta/.codex/worktrees/2bdc/Quackathon` | Real Codex app thread with thread ID, search, deep link, and optional pinning | Default for this project because the user wants sessions visible and monitorable in the Codex app |
| Manual Git worktree | Project-local path such as `.worktrees/c2-data-memory` | Plain Git checkout; app visibility depends on manually opening/launching a separate Codex session there | Advanced fallback when explicit branch checkout/location control matters more than native app-managed lifecycle |

Manual worktree creation usually looks like:

```bash
git worktree add -b ws/c2-data-memory .worktrees/c2-data-memory main
```

This creates a normal branch and checkout. It can be useful, but it changes the operating model:

- The orchestrator owns branch creation and cleanup.
- The user or orchestrator must open/launch a separate Codex session in that worktree for app-visible work.
- Branches cannot be checked out in multiple worktrees at once.
- Manual worktrees should not be the default when the user's requirement is to see each worker inside the Codex app.

For this project, prefer Codex app-managed worktree threads. Use manual `.worktrees/...` only as an explicit fallback after discussing the tradeoff.

## Visibility Protocol

Every spawned worktree session must have:

- A clear `Quackathon C<checkpoint> <lane>` thread title.
- A recorded thread ID.
- A recorded worktree cwd.
- A `codex://threads/<thread-id>` link shared with the user.
- A status row in the orchestrator notes or final checkpoint report.
- Optional pinning only when the user wants pinned visibility or when cleanup protection matters.

If a session is not visible in the sidebar:

1. Search in Codex with `Cmd+G` using the `Quackathon C...` title.
2. Open the direct `codex://threads/<thread-id>` link.
3. Use the app thread registry via `list_threads` to verify whether the session exists.
4. Use `git worktree list --porcelain` to verify whether a worktree exists.
5. If there is a failed pending card but no thread ID, assume setup failed and create a fresh correctly configured worktree thread.

The sidebar is a convenience view, not the source of truth. An unpinned worktree thread may briefly appear, disappear, and reappear as the app reconciles pending worktree setup, active/idle status, project grouping, search state, or sidebar rendering. That flicker is acceptable only when:

- `list_threads` returns the thread ID.
- The `codex://threads/<thread-id>` link opens the thread.
- `git worktree list --porcelain` shows the corresponding worktree.
- The thread status is sensible, for example `active` while running or `idle` after completion.

It is not acceptable if the thread has no ID, cannot be found by app search, cannot be opened by direct link, and has no Git worktree. Treat that case as failed creation, not hidden background work.

## Visibility Test On 2026-06-21

A deliberately read-only test worktree was launched after correcting the protocol.

| Field | Value |
| --- | --- |
| Thread title | `Quackathon Worktree Visibility Test` |
| Thread ID | `019eeb09-28f2-7e42-8ddb-1a5777ab0701` |
| Deep link | `codex://threads/019eeb09-28f2-7e42-8ddb-1a5777ab0701` |
| Worktree | `/Users/abhinavgupta/.codex/worktrees/2bdc/Quackathon` |
| Starting ref | `main` |
| Pin state | intentionally not pinned for natural project visibility testing |
| Result | thread registered successfully, ran, reported, and stopped idle |
| Git state reported by thread | detached HEAD, `git status --short --branch` showed `## HEAD (no branch)` |

Outcome:

- Project-scoped worktree creation from existing `main` works.
- `create_thread` first returned a `pendingWorktreeId`, then the thread appeared in `list_threads` with a real thread ID and worktree cwd.
- Detached HEAD is confirmed as the normal Codex-managed worktree state.
- No files were edited, no commits were created, no `.env` was read, and no network calls were run.
- This test was intentionally left unpinned to test natural project visibility.
- The user observed that the sidebar entry appeared, disappeared, and reappeared. The app registry still returned the thread as `idle`, so the correct interpretation is sidebar flicker/reconciliation rather than lost work.

## Orchestrator Review Lessons

The attached prior-project orchestration summary reinforced these process rules:

- Split work only after source-of-truth docs and contracts are clear.
- Assign narrow file ownership per worker to prevent merge chaos.
- Require structured handoffs from every worker: thread ID, worktree, branch or detached state, files changed, commands run, tests run, risks, and integration notes.
- Treat worker summaries as claims, not proof. The master session must inspect diffs, logs, status, and tests before merging.
- Use `multi_tool_use.parallel` for independent read-only checks, but keep writes, merges, commits, and pushes serialized.
- Prefer integration branches or integration worktrees when combining risky changes.
- Verify the integrated product, not just isolated worker success.
- Preserve evidence for hackathon-critical integrations: commits, health checks, provider status, screenshots or local QA notes, and reasons for rejecting unsafe generated PRs.
- Do not equate "many sessions running" with good orchestration. The value is clear contracts, isolated ownership, skeptical review, and real verification.

For pushing from an isolated worktree directly to a shared branch, the prior project used a fast-forward discipline:

```bash
git fetch origin main
git merge-base --is-ancestor origin/main HEAD
git push origin HEAD:main
```

For this project, the master session should prefer reviewing and merging into local `main` first when practical. Direct `HEAD:main` pushes are allowed only when the branch has been reviewed, the fast-forward check passes, and dirty local checkout state would otherwise make a normal local merge less reliable.
