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
twin-subactor serve --host 127.0.0.1 --port 8188
```

`--offline` disables GitHub and Control reads while retaining local discovery.
Organization roots can be overridden with the environment names in
[`config/sources.json`](config/sources.json). Tokens are read from
`GITHUB_TOKEN` and `SUBACTOR_ADMIN_TOKEN` only for request headers.
The Platform deployment mounts the five organization roots read-only and passes
their container paths through these variables. Standalone containers must do
the same explicitly.

The service exposes `GET /health`, `/v1/snapshot`, `/v1/diagnoses` and
`/v1/next-actions`. All endpoints are read-only and return `Cache-Control:
no-store`.

See [architecture and authority boundaries](docs/ARCHITECTURE.md).
