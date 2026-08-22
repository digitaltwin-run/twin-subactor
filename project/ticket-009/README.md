# Ticket 009: Project purpose into bounded next-process token stream

- **ID**: ticket-009
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-08-22

## Goal and scope

Add a read-only evolutionary projection that binds the current ecosystem Twin
and an accepted existential-purpose DSL into one deterministic next-process
token. The token may describe observation, diagnosis, a Founder interaction or
a governed handoff, but cannot itself execute a mutation.

## Acceptance criteria

- [ ] AC-01: An accepted purpose DSL and identical snapshot produce an
  identical decision digest.
- [ ] AC-02: Every emitted token is bound to purpose, snapshot, previous token
  and selected finding/action evidence.
- [ ] AC-03: A human-routed finding produces a Founder-interaction proposal;
  an empty candidate set produces event-driven wait.
- [ ] AC-04: The adapter chain explicitly separates NL interpretation,
  deterministic DSL selection, URI binding, execution and EQL receipt.
- [ ] AC-05: CLI supports one-shot validation and a non-busy event-driven
  continuous stream without acquiring controller authority.
- [ ] AC-06: Unit and governance checks pass before protected publication.

## Participants

- Human participant: unresolved; no user-* file was created by this script.
- Agent participant: [ai-codex.md](ai-codex.md)
