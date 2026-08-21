# Ticket 002: Tolerate document-shaped VERSION carriers

- **ID**: ticket-002
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-08-21

## Goal and scope

Keep repository observation available when a repository uses `VERSION` as a
bounded Markdown document instead of a short scalar. Extract an explicit
semantic version when present, but never fail or discard the whole repository
because the carrier is document-shaped or has no parseable scalar.

## Acceptance criteria

- [x] AC-01: A bounded document-shaped `VERSION` yields its explicit semantic
  version without failing repository observation.
- [x] AC-02: An unparseable but bounded `VERSION` yields no declared version
  while preserving Git, carrier and ticket evidence for the repository.
- [x] AC-03: The regression test reproduces the observed
  `intent-contract-dsl-runtime` carrier shape without reading that repo during CI.
- [x] AC-04: Unit tests and governance pass before exact-head publication.

## Validation evidence

- Eight unit tests pass, including document-shaped and unparseable VERSION
  carriers.
- The live local snapshot now reports the required Subactor source `healthy`,
  observes 171 repositories, extracts `0.12.0` for the original target and
  emits zero `TWIN-REPOSITORY-OBSERVATION-FAILED` findings.
- The repair changes only the source adapter and its regression tests; it does
  not mutate the observed repository or widen authority.

## Participants

- Human participant: unresolved; no user-* file was created by this script.
- Agent participant: [ai-codex.md](ai-codex.md)
