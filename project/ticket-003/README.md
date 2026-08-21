# Ticket 003: Mark anonymous GitHub discovery as partial

- **ID**: ticket-003
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-08-21

## Goal and scope

Represent unauthenticated GitHub HTTP discovery as `partial/public-only`, even
when the endpoint returns a successful empty or non-empty list. Only a working
authenticated client may claim complete remote organization health. Do not
request, log or infer a credential.

## Acceptance criteria

- [ ] AC-01: Anonymous HTTP discovery retains public repository observations
  but reports source status `partial` with explicit public-only scope.
- [ ] AC-02: Authenticated HTTP and successful authenticated `gh` discovery may
  continue to report `healthy`.
- [ ] AC-03: Empty anonymous results never claim a private organization is
  completely observed.
- [ ] AC-04: Unit, live container and governance checks pass before publication.

## Participants

- Human participant: unresolved; no user-* file was created by this script.
- Agent participant: [ai-codex.md](ai-codex.md)
