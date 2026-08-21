# Ticket 007: Deduplicate unreadable governance carrier findings

- **ID**: ticket-007
- **Owner**: unresolved:human
- **Status**: DONE
- **Workflow state**: DONE
- **Created**: 2026-08-21

## Goal and scope

Keep diagnosis cardinality honest when the governance manifest is also an SSOT
carrier. The hardened live scan currently emits both
`TWIN-GOVERNANCE-UNREADABLE` and `TWIN-SSOT-INVALID` for each of the same 20
permission-denied files. An unreadable file is not evidence of invalid content,
and one observation defect must not become two queue items.

The repair preserves generic unreadable-carrier evidence for non-governance
SSOT paths and retains invalid-content findings for carriers that were read but
failed bounded parsing.

## Acceptance criteria

- [x] AC-01: Permission errors produce carrier status `unreadable`, not `invalid`.
- [x] AC-02: An unreadable governance manifest produces exactly one finding.
- [x] AC-03: A distinct unreadable SSOT carrier produces a stable Doctor finding.
- [x] AC-04: Invalid readable content remains `TWIN-SSOT-INVALID`.
- [x] AC-05: Unit, governance and hardened live deduplication checks pass.
- [x] AC-06: Exact-head Validator performs protected publication.

## Validation evidence

- 19 unit tests pass, including governance-path deduplication, a distinct
  unreadable SSOT carrier and invalid readable JSON.
- Exact-base governance reports zero errors and zero warnings.
- A non-root, read-only, capability-free image scanned the live organization
  roots: 20 governance-unreadable findings, zero SSOT-invalid findings, zero
  generic SSOT-unreadable findings for the owned manifest paths and zero target
  intersections. Finding total fell from the duplicate-inflated shape without
  changing observed files.

## Publication evidence

- Pull request: `subactor/twin-subactor#13`.
- Frozen and approved head: `e127a1d4cba98f97d65c57171fe2abf5038f667f`.
- Hosted CI and governance checks passed on the frozen head.
- Validator run: `32469962427`; review: `4992116274`.
- Merge commit: `056dfec9e9b4b04fc3abe5ee6305c91898adb3fa`;
  merged `2026-08-21T09:54:27Z`.

## Integrated live evidence

The read-only service was rebuilt from merged commit `056dfec`. Snapshot
`sha256:0145332898402d791c8b87b5d83c282db65aafc3f6dd581bc83c0d87035b93fa`
observes 173 repositories and 147 findings: 20 governance-unreadable, zero
SSOT-invalid duplicates, zero generic SSOT-unreadable duplicates, zero empty
registry and zero repository-observation failures. Registry parity remains
25 entries, 148 state variables and three policy evaluations.

## Closure boundary

This governance-only closure records the integrated result. It changes no Twin
runtime, registry, observed repository or authority boundary.

## Authorization

The request to continue autonomy and Twin correctness testing is
`SESSION_EXECUTION_AUTHORIZATION` for this bounded diagnosis repair and its
protected publication. It grants no repository mutation or direct merge authority.

## Participants

- Human participant: unresolved; no user-* file was created by this script.
- Agent participant: [ai-codex.md](ai-codex.md)
