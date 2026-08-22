# Ticket 009: Project purpose into bounded next-process token stream

- **ID**: ticket-009
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-08-22

## Goal and scope

Add a read-only evolutionary projection that binds the current ecosystem Twin
and an accepted existential-purpose DSL into one deterministic next-process
token. The token may describe observation, diagnosis, a Founder interaction or
a governed handoff, but cannot itself execute a mutation.

## Acceptance criteria

- [x] AC-01: An accepted purpose DSL and identical snapshot produce an
  identical decision digest.
- [x] AC-02: Every emitted token is bound to purpose, snapshot, previous token
  and selected finding/action evidence.
- [x] AC-03: A human-routed finding produces a Founder-interaction proposal;
  an empty candidate set produces event-driven wait.
- [x] AC-04: The adapter chain explicitly separates NL interpretation,
  deterministic DSL selection, URI binding, execution and EQL receipt.
- [x] AC-05: CLI supports one-shot validation and a non-busy event-driven
  continuous stream without acquiring controller authority.
- [x] AC-06: Unit, schema, lint and governance checks pass before protected
  publication.

## Validation evidence

- 26 unit tests pass, including deterministic decisions, hash chaining,
  purpose-conditioned tie-breaking, Founder interaction, event-driven wait and
  fail-closed purpose validation.
- Both JSON documents validate against their Draft 2020-12 schemas.
- The real offline ecosystem snapshot produced decision
  `sha256:28859e14d264cbf4014b9b463822eda24b03c8b7181ae3ad90e80c8de32e842f`:
  `request-founder-decision` for `repo:subactor/views`, with
  `twinMayAct=false`.
- Exact-base governance passes with zero errors and zero warnings. Its earlier
  secret-name false positive was resolved by removing credential-like local
  variable names, without weakening the scanner.

## Audit evidence

- Diagit observed 72 Subactor repositories and 158 findings: 40 errors, all
  worktree overlaps; the main hotspots are `www-sub-actor`, `queue-agent`,
  `core` and `validator-agent`.
- Todocs observed 65 projects and 139,510 SLOC, but its default depth reports
  `core` as having no tests even though its test suite lives below depth three.
  The result is structural portfolio evidence, not a sufficient health oracle.
- The live Twin discovered all configured local and GitHub organizations but
  correctly marked required Control read models unavailable without its
  dedicated header credential and proposed a Doctor handoff.

## Authorization

The user's request to analyze the ecosystem and build the bounded organism
prototype is `SESSION_EXECUTION_AUTHORIZATION`. It does not authorize Twin to
execute a mutation, invent an exact runtime URI or approve its own result.

## Participants

- Human participant: unresolved; no user-* file was created by this script.
- Agent participant: [ai-codex.md](ai-codex.md)
