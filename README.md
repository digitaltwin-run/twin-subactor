# twin-subactor

Read-only, rebuildable Digital Twin of the entire Subactor ecosystem. It
discovers configured GitHub organizations and local workspaces, consumes
declared source-of-truth carriers plus existing Control read models, and emits
content-addressed diagnoses and ranked next-action candidates.

The repository is HOME in `subactor` and ADOPTS Wellmanifest standards. It does
not own controller scheduling, repair execution, credentials, authority or PR
approval. Every mutation remains a separate, digest-bound
Doctor → Repair → Validator process.

## Use

```bash
python -m pip install -e .
twin-subactor snapshot
twin-subactor diagnose
twin-subactor recommend
twin-subactor watch --interval 15
twin-subactor --offline evolve --purpose docs/examples/subactor-purpose.v1.json --once
twin-subactor serve --host 127.0.0.1 --port 8188
```

`evolve` treats an accepted existential-purpose DSL as durable context and
emits one hash-chained next-process token whenever the Twin decision changes.
Without `--once` it remains alive but does not emit a busy-loop stream while
the snapshot is unchanged. The example purpose preserves the original NL and
its accepted typed constraints.

The token's `projectionUri` addresses a read-only Twin transition. It is not an
executable connector URI. `runtimeBinding.status` remains
`requires-control-catalog-binding` until Control resolves an allowed capability
to an exact registered URI. The chain is deliberately split into NL → accepted
DSL, environment → DOQL/Twin facts, deterministic selection, catalog binding,
AQL/grant, execution and independent EQL/receipt. Twin never performs the last
four steps.

`--offline` disables GitHub and Control reads while retaining local discovery.
Organization roots can be overridden with the environment names in
[`config/sources.json`](config/sources.json). Tokens are read from
`GITHUB_TOKEN` and `SUBACTOR_ADMIN_TOKEN` only for request headers.
The Platform deployment mounts the six organization roots read-only and passes
their container paths through these variables. Standalone containers must do
the same explicitly.

The organization roles are deliberately separate: Subactor owns product
runtime, Wellmanifest owns adopted standards, Semcod contributes code and
intent evidence tools, and Autogrammar contributes typed grammar and DSL
tooling. Optional `uri-twin` and `oqlos` roots remain infrastructure-observation
and typed-query sources. These roles classify evidence; they do not grant
repair, repository-transfer or merge authority.

The service exposes `GET /health`, `/v1/snapshot`, `/v1/diagnoses` and
`/v1/next-actions`. All endpoints are read-only and return `Cache-Control:
no-store`.

See [architecture and authority boundaries](docs/ARCHITECTURE.md).
