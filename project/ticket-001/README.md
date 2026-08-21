# Ticket 001: Build the Subactor ecosystem Digital Twin

- **ID**: ticket-001
- **Owner**: unresolved:human
- **Status**: DONE
- **Workflow state**: DONE
- **Created**: 2026-08-21

## Goal and scope

Create the first ecosystem-wide, read-only Digital Twin for Subactor. Discover
declared repositories, inspect bounded source-of-truth carriers, combine them
with the existing Control Digital Twin read models and emit a rebuildable,
content-addressed snapshot plus deterministic diagnoses and ranked next-action
candidates.

The Twin is not a second controller. It does not schedule work, mutate a target,
grant repair authority, invoke a shell from model output or approve a pull
request. Doctor, Repair and Validator remain separate stages and every proposed
handoff is bound to the snapshot and finding digests.

## Acceptance criteria

- [x] AC-01: Local and GitHub organization discovery represents every observed
  repository with provenance, freshness and source-health state.
- [x] AC-02: The snapshot consumes only declared SSOT carriers and bounded
  Control read models; unavailable inputs are `unknown`, never healthy.
- [x] AC-03: Deterministic rules emit deduplicated, prioritized next-action
  candidates bound to snapshot and finding digests.
- [x] AC-04: Repairable candidates express `doctor → repair → validator`
  handoffs without embedding authority or executing effects.
- [x] AC-05: A read-only CLI and HTTP service expose snapshot, diagnosis and
  next-action projections and run in a non-root, read-only container.
- [x] AC-06: Unit, governance, container and live read-only smoke tests pass.
- [x] AC-07: Publication uses exact-head Validator approval and protected merge.

## Publication evidence

- Pull request: `subactor/twin-subactor#1`.
- Frozen and approved head: `b25eead079aa52d1518c258c9ee90c3dcf7ceed2`.
- Validator run: `32459586673`; review: `4990924981`.
- Merge commit: `d60ad68`; merged `2026-08-21T07:41:33Z`.
- The protected delivery process deleted the remote implementation branch.

## Closure boundary

This governance-only closure records the already integrated result. It changes
no Twin runtime, contract, container, source inventory or authority boundary.

## Participants

- Human participant: unresolved; no user-* file was created by this script.
- Agent participant: [ai-codex.md](ai-codex.md)
