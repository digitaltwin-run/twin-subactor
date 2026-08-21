# Ticket 006: Project nested Control registry cardinalities

- **ID**: ticket-006
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-08-21

## Goal and scope

Make the bounded Control system-state projection report semantic registry
cardinalities and nested schemas. The current implementation counts envelope
keys, so a live registry with 24 services, one process, 148 variables and three
evaluations is misrepresented as `4/3/9` with a null schema.

The fix remains summary-only: Twin does not retain arbitrary Control payloads,
mutate registry state or gain execution authority.

## Acceptance criteria

- [x] AC-01: Registry count equals services plus processes, not envelope keys.
- [x] AC-02: State-variable count equals nested variables and policy count
      equals nested evaluations.
- [x] AC-03: Nested registry schemas are preserved in the bounded projection.
- [x] AC-04: Unit, governance and live Control/Twin parity checks pass.
- [ ] AC-05: Exact-head Validator performs protected publication.

## Validation evidence

- 17 unit tests pass, including an exact nested system-state fixture.
- Exact-base governance reports zero errors and zero warnings.
- Applying the new bounded summarizer directly to the authenticated live Control
  response yields: 25 registry entries (24 services + 1 process), 148 state
  variables and 3 policy evaluations. All three nested schemas are preserved.
- No full Control payload or credential was logged or retained.

## Authorization

The request to continue, update the registry and verify Twin correctness is
`SESSION_EXECUTION_AUTHORIZATION` for this bounded projection repair and its
protected publication. It grants no Control mutation or direct merge authority.

## Participants

- Human participant: unresolved; no user-* file was created by this script.
- Agent participant: [ai-codex.md](ai-codex.md)
