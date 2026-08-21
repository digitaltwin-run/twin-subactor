# Ticket 004: Detect fail-open worktree guard drift

- **ID**: ticket-004
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-08-21

## Goal and scope

Teach the ecosystem Twin to distinguish four worktree-guard states in every
local governed repository: absent runner, untracked managed files, unwired hook
and a hook fragment that still fails open when its runner disappears.

The observation is bounded and read-only. It records paths and booleans only;
it does not execute hooks, inspect file contents beyond the small hook contract,
install governance files or grant Repair authority.

## Acceptance criteria

- [ ] AC-01: A configured fail-open hook produces
      `TWIN-WORKTREE-GUARD-FAIL-OPEN`.
- [ ] AC-02: Missing and untracked runners have distinct stable error codes.
- [ ] AC-03: A complete tracked, wired, fail-closed guard produces no guard
      finding.
- [ ] AC-04: Unit tests and exact-base governance pass before Validator review.

## Authorization

The request to investigate the recurring guard failure and continue autonomy
testing is `SESSION_EXECUTION_AUTHORIZATION` for this bounded read-only detector
and protected publication. Mutation of observed repositories still requires a
separate digest-bound grant.

## Participants

- Human participant: unresolved; no user-* file was created by this script.
- Agent participant: [ai-codex.md](ai-codex.md)
