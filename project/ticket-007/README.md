# Ticket 007: Deduplicate unreadable governance carrier findings

- **ID**: ticket-007
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
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
- [ ] AC-06: Exact-head Validator performs protected publication.

## Validation evidence

- 19 unit tests pass, including governance-path deduplication, a distinct
  unreadable SSOT carrier and invalid readable JSON.
- Exact-base governance reports zero errors and zero warnings.
- A non-root, read-only, capability-free image scanned the live organization
  roots: 20 governance-unreadable findings, zero SSOT-invalid findings, zero
  generic SSOT-unreadable findings for the owned manifest paths and zero target
  intersections. Finding total fell from the duplicate-inflated shape without
  changing observed files.

## Authorization

The request to continue autonomy and Twin correctness testing is
`SESSION_EXECUTION_AUTHORIZATION` for this bounded diagnosis repair and its
protected publication. It grants no repository mutation or direct merge authority.

## Participants

- Human participant: unresolved; no user-* file was created by this script.
- Agent participant: [ai-codex.md](ai-codex.md)
