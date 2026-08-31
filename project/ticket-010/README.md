# Ticket 010: Build account-scoped SQLite Digital Twin and URI connector

- **ID**: ticket-010
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-08-31

## Goal and scope

Create the `twin-subactor-account` profile as a local, rebuildable projection of
one Subactor account. It must combine bounded API observations with local
organization, repository and project-manifest evidence, preserve provenance,
and support research and recovery without becoming a new operational source of
truth.

The projection owns one SQLite file only. It must not copy or attach existing
Planfile, Org Core, account-inventory or service SQLite databases. A rebuild
creates a complete candidate database and atomically replaces the prior
projection only after validation.

## Acceptance criteria

- [x] AC-01: One account-scoped SQLite projection stores organizations,
  repositories, projects, tickets and other configured API resources with
  source receipts, canonical payload digests and no credentials.
- [x] AC-02: Local discovery resolves active top-level repositories and bounded
  nested legacy project manifests, including an explicit local path and
  location state.
- [x] AC-03: Rebuild is atomic and unavailable/disabled sources remain visible;
  a failed candidate never destroys the last valid projection.
- [x] AC-04: Fixed CLI and read-only HTTP queries expose summaries, sources,
  entity types and a bounded project/ticket research matrix.
- [x] AC-05: Unit, schema, real offline rebuild and exact-head governance checks
  pass before protected publication.

## Validation evidence

- 32 unit tests pass, including atomic candidate failure, API redaction, missing
  declared project paths, CLI/HTTP parity and project-ticket combinations.
- A Draft 2020-12 validation accepted the real offline summary; it observed 6
  organizations, 255 repositories, 38 project observations and 20 deployment
  bindings without copying an existing SQLite file.
- A hardened `--read-only`, non-root container rebuilt the projection under
  `/data`; one unreadable workspace entry degraded the source to `partial`
  without losing readable repositories.
- A real Twin HTTP process and the real urirun connector returned
  `wydruk-subactor-com` through `twin://subactor/account/query/projects`, with
  source `platform-site-resources` and state `declared-path-missing`.
- The Subactor connector registry loaded all 10 account routes with zero
  failures and zero unresolved duplicates.

## Project placement observation

- Active local repositories: `workspace://subactor/c2004-mask-services` and
  `workspace://subactor/founder-subactor-com`.
- No current `workspace://subactor/projekty` directory exists.
- `platform/config/site-resources.json` still declares both Founder and Wydruk
  below that removed directory. Wydruk has no current local code directory;
  Founder has moved to a top-level repository. The Twin preserves this drift.
- Subactor Shell implements `projects`, `projects --recon` and `/projects
  [recon]`. The inspected local CLI could not call the live API because it had
  no active session; the command itself is present and covered by tests.

## Authorization

The user's instruction to investigate project placement and implement the
account Twin, SQLite projection and URI connector is
`SESSION_EXECUTION_AUTHORIZATION`. It authorizes material implementation and
protected publication, but not destructive changes to source systems, secret
intake or treating failed observations as healthy.

## Participants

- Human participant: the requesting Founder in this session; no user-* file
  was created because the instruction is already preserved in the session.
- Agent participant: [ai-codex.md](ai-codex.md)
