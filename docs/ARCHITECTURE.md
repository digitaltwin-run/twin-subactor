# Ecosystem Twin architecture

`twin-subactor` is an observational runtime service HOME in Subactor. It ADOPTS
Wellmanifest contracts and consumes declared source-of-truth carriers; it does
not make Wellmanifest a runtime owner.

```text
GitHub organizations ─┐
local Git workspaces ─┼─> bounded source adapters ─> rebuildable snapshot
Control read models ──┘                                  │
                                                        ├─> diagnoses
                                                        └─> ranked next actions
                                                               │ advisory only
                    Control / queue-agent <─ ticket/process ────┘
                               │
                       doctor → repair → validator
```

The repository registry declares organization roles. A role is never inferred
from a repository name. Every repository is represented even when it has no
recognized semantic carrier; missing and invalid carriers become evidence.
Remote and local observations are merged by the GitHub full name.

The snapshot stores only bounded summaries, hashes, Git topology, ticket-state
counts and declared manifest fields. Credentials remain environment-only HTTP
headers and never enter a snapshot, URL, exception or log. An unavailable
source is `unavailable` or `partial`, never an empty healthy result.

Next-action policy is deterministic first. Severity, required-source impact and
stable tie-breaking produce the priority. The embedded DSL is a typed advisory
request with opaque target and evidence references. An LLM may rank candidates
that have the same deterministic score; it cannot add an operation, target,
authority or evidence body.

Mutation requires a separate grant bound to the snapshot and finding digests.
Repair consumes a declared skills-agent process, and Validator consumes the
exact repair result. Dirty worktrees, secret handling, stash decisions and
ambiguous ownership are always routed to a human decision rather than repair.

## Low-level boundary assessment

The current Subactor scheduler is already a separate low-level module with one
clock and ticket-per-occurrence semantics. Control remains its composition root
and starts controllers from `server.mjs`; therefore extraction is partial, not
complete. This Twin deliberately connects through Control read models and a
read-only service interface. It does not import Control internals, start another
scheduler or own an event store. A later extraction may move controller startup
into a dedicated runtime composition package without changing this contract.
