---
participant-id: agent:codex
participant: codex
role: agent
ticket: ticket-010
---
# Participant: codex (AI agent)

## Understanding

The account Twin is a recovery and research projection, not a fourth account,
ticket or project authority. It should preserve full bounded source records
after secret-field redaction, make source gaps explicit and permit deterministic
cross-resource analysis from one disposable SQLite file.

## Execution plan

1. Inventory existing project locations, Shell commands and SQLite owners.
2. Extend the existing Twin with bounded local/API account observations.
3. Build and atomically swap one normalized SQLite projection.
4. Add CLI and HTTP query adapters over the same projection.
5. Verify real offline discovery, failure semantics and exact-head governance.

## Actual changes

- Initialized the bounded ticket and recorded SESSION_EXECUTION_AUTHORIZATION
  from the request to execute this work.
- Confirmed that current project repositories live at the Subactor workspace
  top level while an explicitly named legacy tree contains prior layouts.
- Confirmed that Subactor Shell implements `projects` and `projects --recon`;
  the local invocation is currently blocked by the absence of an active CLI
  session, not by a missing command.
- Selected `subactor/twin-subactor` as HOME and a projection-only SQLite model
  so existing operational stores are neither copied nor replaced.
- Added account-scoped source adapters, normalized SQLite entities/views,
  integrity-checked atomic replacement and deterministic query projections.
- Added managed site-resource and deployment-binding observations after a real
  rebuild proved that an absent local project tree would otherwise hide the
  still-declared `wydruk.subactor.com` project.
- Added CLI and read-only HTTP resources over the same database; the container
  can rebuild once on startup and writes only to its dedicated `/data` mount.
- Made local repository discovery permission-tolerant after the hardened image
  exposed an unreadable `.publication-state` entry; the receipt is `partial`
  instead of aborting the complete projection.
- Proved the complete Twin HTTP → urirun query path with a real process and a
  real 568 KiB SQLite candidate, not a mocked transport.

## Blockers

- None inside the recorded intent; proceed without a second confirmation.
- New authority remains required for destructive action, secret access, new
  external coordination or material objective expansion. Protected delivery
  may be invoked without another prompt when publication is in scope; its
  exact-head trusted approval remains independent evidence.
