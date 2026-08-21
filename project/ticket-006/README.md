# Ticket 006: Project nested Control registry cardinalities

- **ID**: ticket-006
- **Owner**: unresolved:human
- **Status**: DONE
- **Workflow state**: DONE
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
- [x] AC-05: Exact-head Validator performs protected publication.

## Validation evidence

- 17 unit tests pass, including an exact nested system-state fixture.
- Exact-base governance reports zero errors and zero warnings.
- Applying the new bounded summarizer directly to the authenticated live Control
  response yields: 25 registry entries (24 services + 1 process), 148 state
  variables and 3 policy evaluations. All three nested schemas are preserved.
- No full Control payload or credential was logged or retained.

## Publication evidence

- Pull request: `subactor/twin-subactor#11`.
- Frozen and approved head: `07468986ab835a99ace14708ff1d684978415962`.
- Hosted CI and governance run: `32469030000` and `32469030014`.
- Validator run: `32469094110`; review: `4992002933`.
- Merge commit: `3688a2bbb34d998b4a0e894d699b7aba9644d34d`;
  merged `2026-08-21T09:43:36Z`.

## Integrated live evidence

The read-only service was rebuilt from merged commit `3688a2b`. Snapshot
`sha256:4455d56e1ba672d2d4768fa30f3b845daec79ff479f5367f870bfcd88a9948b3`
observed 173 repositories and now exposes the exact Control values: 25 registry
entries (24 services + one process), 148 state variables and three policy
evaluations. It reports zero empty-registry and zero repository-observation
failure findings.

## Closure boundary

This governance-only closure records the integrated result. It changes no Twin
runtime, registry, observed repository or authority boundary.

## Authorization

The request to continue, update the registry and verify Twin correctness is
`SESSION_EXECUTION_AUTHORIZATION` for this bounded projection repair and its
protected publication. It grants no Control mutation or direct merge authority.

## Participants

- Human participant: unresolved; no user-* file was created by this script.
- Agent participant: [ai-codex.md](ai-codex.md)
