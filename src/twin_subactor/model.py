from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .diagnosis import diagnose, next_actions
from .sources import digest, discover_local, discover_remote, load_config, observe_control


def _merge_repositories(local: list[dict[str, Any]], remote: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for repository in [*remote, *local]:
        current = merged.setdefault(repository["id"], {"id": repository["id"]})
        for key, value in repository.items():
            if key == "id":
                continue
            if key in {"local", "remote"}:
                current[key] = bool(current.get(key)) or bool(value)
            else:
                current[key] = value
    return [merged[key] for key in sorted(merged)]


def build_snapshot(config_path: Path, *, offline: bool = False) -> dict[str, Any]:
    config_path = config_path.resolve()
    repository_root = config_path.parent.parent
    config = load_config(config_path)
    local_sources, local_repositories = discover_local(config, repository_root)
    remote_sources, remote_repositories = discover_remote(config, offline)
    control_sources, control = observe_control(config, offline)
    repositories = _merge_repositories(local_repositories, remote_repositories)
    sources = sorted([*local_sources, *remote_sources, *control_sources], key=lambda item: (item["kind"], item["id"]))
    semantic_projection: dict[str, Any] = {
        "schema": "subactor.ecosystem-twin.snapshot/v1",
        "sources": sources,
        "repositories": repositories,
        "control": control,
    }
    projection: dict[str, Any] = {
        **semantic_projection,
        "capturedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "snapshotDigest": digest(semantic_projection),
    }
    projection["findings"] = diagnose(projection, config)
    projection["nextActions"] = next_actions(projection, config)
    return projection
