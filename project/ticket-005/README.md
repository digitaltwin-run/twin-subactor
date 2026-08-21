# Ticket 005: Distinguish unreadable governance carriers

- **ID**: ticket-005
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-08-21

## Goal and scope

Keep ecosystem observation truthful when a governance manifest is present but
unreadable to the hardened Twin container. Preserve the bounded read-only
contract and report this as an observation defect rather than falsely claiming
that governance is missing.

## Acceptance criteria

- [ ] AC-01: A missing manifest remains `TWIN-GOVERNANCE-MISSING`.
- [ ] AC-02: An unreadable manifest produces a distinct stable diagnosis and
      never produces `TWIN-GOVERNANCE-MISSING`.
- [ ] AC-03: A readable valid manifest preserves the current projection.
- [ ] AC-04: Unit tests, governance and a live hardened-container check pass.
- [ ] AC-05: Publication uses exact-head Validator approval and protected merge.

## Authorization

The request to continue, update the registry and verify autonomy and the Twin
is `SESSION_EXECUTION_AUTHORIZATION` for this bounded detector repair and its
protected publication. It does not authorize mutation of observed repositories.

## Participants

- Human participant: unresolved; no user-* file was created by this script.
- Agent participant: [ai-ai-codex.md](ai-ai-codex.md)
