# Ticket 008: Add Autogrammar as an ecosystem source

- **ID**: ticket-008
- **Owner**: unresolved:human
- **Status**: DONE
- **Workflow state**: DONE
- **Created**: 2026-08-21

## Goal and scope

Make the configured ecosystem match the four active local organizations by
adding Autogrammar as a first-class, read-only grammar and DSL source. Preserve
the optional `uri-twin` and `oqlos` sources because they exist locally and have
distinct infrastructure/query roles.

## Acceptance criteria

- [x] AC-01: Autogrammar is declared with a closed organization id, role and
  overridable workspace root.
- [x] AC-02: Local and remote Twin discovery includes Autogrammar without
  granting it governance or mutation authority.
- [x] AC-03: Unit and governance checks pass.
- [x] AC-04: Platform can mount the organization root separately under a
  follow-up Platform ticket.

## Validation evidence

- All 20 unit tests pass, including the production role and root contract.
- An offline live snapshot observes 36 Autogrammar repositories with a healthy
  source receipt and digest
  `sha256:93de766f50cd0036adceb7e52b5a24455e170af9f35e58423a62acb38bee400a`.
- Exact-base governance passes with zero errors and zero warnings.

## Publication evidence

- Pull request: `subactor/twin-subactor#15`.
- Frozen and approved head: `2fbe290e28bc009f4ea7c6b902a26fe6cd432226`.
- Trusted review: `ifuri-validator-agent[bot]`, exact-head `APPROVED`.
- Merge commit: `e42bec4b51470c338da75af688844f5b39dfb432`.

## Closure boundary

This commit records the integrated result only. It changes no source adapter,
observed repository or authority boundary.

## Authorization

The request to inspect and improve the integration of all four organizations is
`SESSION_EXECUTION_AUTHORIZATION` for this bounded source-registration change.
It does not authorize repository transfers, deletion of duplicate clones or a
direct merge.

## Participants

- Human participant: unresolved; no user-* file was created by this script.
- Agent participant: [ai-codex.md](ai-codex.md)
