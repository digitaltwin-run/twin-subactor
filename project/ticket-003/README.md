# Ticket 003: Mark anonymous GitHub discovery as partial

- **ID**: ticket-003
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-08-21

## Goal and scope

Represent unauthenticated GitHub HTTP discovery as `partial/public-only`, even
when the endpoint returns a successful empty or non-empty list. Only a working
authenticated client may claim complete remote organization health. Do not
request, log or infer a credential.

## Acceptance criteria

- [x] AC-01: Anonymous HTTP discovery retains public repository observations
  but reports source status `partial` with explicit public-only scope.
- [x] AC-02: Authenticated HTTP and successful authenticated `gh` discovery may
  continue to report `healthy`.
- [x] AC-03: Empty anonymous results never claim a private organization is
  completely observed.
- [x] AC-04: Unit, live container and governance checks pass before publication.

## Validation evidence

- Ten unit tests pass, including anonymous-empty and authenticated HTTP cases.
- A hardened live container kept both required local sources healthy and marked
  all five anonymous remote observations `partial/public-only`.
- The anonymously empty Subactor remote result is no longer healthy; public
  repositories remain available as bounded evidence.

## Participants

- Human participant: unresolved; no user-* file was created by this script.
- Agent participant: [ai-codex.md](ai-codex.md)
