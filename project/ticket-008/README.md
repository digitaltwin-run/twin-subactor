# Ticket 008: Add Autogrammar as an ecosystem source

- **ID**: ticket-008
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-08-21

## Goal and scope

Make the configured ecosystem match the four active local organizations by
adding Autogrammar as a first-class, read-only grammar and DSL source. Preserve
the optional `uri-twin` and `oqlos` sources because they exist locally and have
distinct infrastructure/query roles.

## Acceptance criteria

- [ ] AC-01: Autogrammar is declared with a closed organization id, role and
  overridable workspace root.
- [ ] AC-02: Local and remote Twin discovery includes Autogrammar without
  granting it governance or mutation authority.
- [ ] AC-03: Unit and governance checks pass.
- [ ] AC-04: Platform can mount the organization root separately under a
  follow-up Platform ticket.

## Authorization

The request to inspect and improve the integration of all four organizations is
`SESSION_EXECUTION_AUTHORIZATION` for this bounded source-registration change.
It does not authorize repository transfers, deletion of duplicate clones or a
direct merge.

## Participants

- Human participant: unresolved; no user-* file was created by this script.
- Agent participant: [ai-codex.md](ai-codex.md)
