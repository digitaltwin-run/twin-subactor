# Ticket 004: Detect fail-open worktree guard drift

- **ID**: ticket-004
- **Owner**: unresolved:human
- **Status**: DONE
- **Workflow state**: DONE
- **Created**: 2026-08-21

## Goal and scope

Teach the ecosystem Twin to distinguish four worktree-guard states in every
local governed repository: absent runner, untracked managed files, unwired hook
and a hook fragment that still fails open when its runner disappears.

The observation is bounded and read-only. It records paths and booleans only;
it does not execute hooks, inspect file contents beyond the small hook contract,
install governance files or grant Repair authority.

## Acceptance criteria

- [x] AC-01: A configured fail-open hook produces
      `TWIN-WORKTREE-GUARD-FAIL-OPEN`.
- [x] AC-02: Missing and untracked runners have distinct stable error codes.
- [x] AC-03: A complete tracked, wired, fail-closed guard produces no guard
      finding.
- [x] AC-04: Unit tests and exact-base governance pass before Validator review.

## Validation evidence

- 13 unit tests pass, including fail-open, missing, untracked, healthy and
  standard-source negative cases.
- Python bytecode compilation passes.
- Exact-base governance reports zero errors and zero warnings.
- Live local observation reports `core` and `platform` healthy and classifies
  `www-sub-actor` as `TWIN-WORKTREE-GUARD-NOT-WIRED`; because that checkout is
  dirty, the finding routes to human rather than inventing repair authority.

## Publication evidence

- Pull request: `subactor/twin-subactor#7`
- Frozen and approved head: `2066bb37ff248228cacfdcc06d8dd01f5ae4c2f7`
- Validator run: `32465104375`
- Validator review: `4991524777`
- Merge commit: `13b3630ce4e693f6df3f09b96badae39b1ab070b`
  (merged `2026-08-21T08:53:05Z`)

## Authorization

The request to investigate the recurring guard failure and continue autonomy
testing is `SESSION_EXECUTION_AUTHORIZATION` for this bounded read-only detector
and protected publication. Mutation of observed repositories still requires a
separate digest-bound grant.

## Participants

- Human participant: unresolved; no user-* file was created by this script.
- Agent participant: [ai-codex.md](ai-codex.md)
