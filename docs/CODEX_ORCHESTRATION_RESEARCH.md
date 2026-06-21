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

These threads were renamed with a `Quackathon C1` prefix and pinned after the visibility diagnosis so the user can find them more easily in the app.

## Correct Future Spawn Protocol

For future batches:

1. Use `list_projects` and target `/Users/abhinavgupta/Desktop/Quackathon`.
2. Use `create_thread` with `environment.type = "worktree"`.
3. Use `startingState.branchName = "main"` unless there is a deliberate reason to start from another existing branch.
4. Do not pass a desired new lane branch as `startingState.branchName`.
5. Treat detached HEAD as normal for native Codex-managed worktrees.
6. Put the logical lane in the title and prompt, for example `Quackathon C2 Data Memory`.
7. Immediately call `set_thread_title`.
8. Immediately call `set_thread_pinned` while the workstream is active.
9. Confirm the thread with `list_threads` and record its ID, title, status, and cwd.
10. Confirm Git worktree registration with `git worktree list --porcelain`.
11. Report the `codex://threads/<thread-id>` link to the user.
12. Monitor the visible thread with `read_thread` or by opening the app thread.
13. Create a Git branch only when the work needs to be committed or pushed from the worktree.
14. Use Handoff if the work should be brought back into the foreground checkout.

## Visibility Protocol

Every spawned worktree session must have:

- A clear `Quackathon C<checkpoint> <lane>` thread title.
- A pinned thread while active.
- A recorded thread ID.
- A recorded worktree cwd.
- A `codex://threads/<thread-id>` link shared with the user.
- A status row in the orchestrator notes or final checkpoint report.

If a session is not visible in the sidebar:

1. Search in Codex with `Cmd+G` using the `Quackathon C...` title.
2. Open the direct `codex://threads/<thread-id>` link.
3. Use the app thread registry via `list_threads` to verify whether the session exists.
4. Use `git worktree list --porcelain` to verify whether a worktree exists.
5. If there is a failed pending card but no thread ID, assume setup failed and create a fresh correctly configured worktree thread.

