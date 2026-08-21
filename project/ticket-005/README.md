# Ticket 005: Distinguish unreadable governance carriers

- **ID**: ticket-005
- **Owner**: unresolved:human
- **Status**: DONE
- **Workflow state**: DONE
- **Created**: 2026-08-21

## Goal and scope

Keep ecosystem observation truthful when a governance manifest is present but
unreadable to the hardened Twin container. Preserve the bounded read-only
contract and report this as an observation defect rather than falsely claiming
that governance is missing.

## Acceptance criteria

- [x] AC-01: A missing manifest remains `TWIN-GOVERNANCE-MISSING`.
- [x] AC-02: An unreadable manifest produces a distinct stable diagnosis and
      never produces `TWIN-GOVERNANCE-MISSING`.
- [x] AC-03: A readable valid manifest preserves the current projection.
- [x] AC-04: Unit tests, governance and a live hardened-container check pass.
- [x] AC-05: Publication uses exact-head Validator approval and protected merge.

## Validation evidence

- 16 unit tests pass, including absent, invalid, unreadable and valid manifests.
- Exact-base governance reports zero errors and zero warnings.
- A non-root, read-only, capability-free container scanned the live organization
  roots and classified 20 permission-denied manifests as
  `TWIN-GOVERNANCE-UNREADABLE`, routed to Doctor. Those repositories no longer
  produce the false `TWIN-GOVERNANCE-MISSING` diagnosis.

## Publication evidence

- Pull request: `subactor/twin-subactor#9`.
- Frozen and approved head: `0ae1d975ad9aa5a40722e632225aa6f5e157ba98`.
- Hosted CI and governance run: `32467889193` and `32467889179`.
- Validator run: `32468220581`; review: `4991880927`.
- Merge commit: `d91941018d32239aa87f39546f0f1bd44d0c4d13`;
  merged `2026-08-21T09:32:30Z`.

## Closure boundary

This governance-only closure records the integrated result. It changes no Twin
runtime, source registry, observed repository or authority boundary.

## Authorization

The request to continue, update the registry and verify autonomy and the Twin
is `SESSION_EXECUTION_AUTHORIZATION` for this bounded detector repair and its
protected publication. It does not authorize mutation of observed repositories.

## Participants

- Human participant: unresolved; no user-* file was created by this script.
- Agent participant: [ai-ai-codex.md](ai-ai-codex.md)
