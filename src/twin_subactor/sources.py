from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ORG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,37}[a-z0-9])?$")
STATUS_RE = re.compile(r"^- \*\*Status\*\*:\s*([A-Z_]+)\s*$", re.MULTILINE)
WORKFLOW_RE = re.compile(r"^- \*\*Workflow state\*\*:\s*([A-Z_]+)\s*$", re.MULTILINE)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def _read_bytes(path: Path, limit: int = 1_048_576) -> bytes:
    with path.open("rb") as handle:
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"source exceeds {limit} bytes")
    return data


def _git(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={root}", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or "git observation failed")
    return result.stdout.strip()


def _origin_full_name(url: str) -> str | None:
    match = re.search(r"(?:github\.com[:/])([^/]+/[^/]+?)(?:\.git)?$", url)
    return match.group(1) if match else None


def _ticket_summary(repo: Path, limit: int) -> dict[str, Any]:
    tickets: list[dict[str, str]] = []
    project = repo / "project"
    if project.is_dir():
        for readme in sorted(project.glob("ticket-*/README.md"))[:limit]:
            text = _read_bytes(readme, 131_072).decode("utf-8", "replace")
            status = STATUS_RE.search(text)
            workflow = WORKFLOW_RE.search(text)
            tickets.append(
                {
                    "id": readme.parent.name,
                    "status": status.group(1) if status else "UNKNOWN",
                    "workflow": workflow.group(1) if workflow else "UNKNOWN",
                }
            )
    counts: dict[str, int] = {}
    for ticket in tickets:
        key = f"{ticket['status']}/{ticket['workflow']}"
        counts[key] = counts.get(key, 0) + 1
    return {"count": len(tickets), "counts": counts, "active": [t for t in tickets if t["status"] == "IN_PROGRESS"]}


def _carrier(repo: Path, relative: str) -> dict[str, Any] | None:
    path = repo / relative
    if not path.is_file():
        return None
    try:
        raw = _read_bytes(path)
        result: dict[str, Any] = {
            "path": relative,
            "status": "valid",
            "digest": "sha256:" + hashlib.sha256(raw).hexdigest(),
        }
        if path.suffix == ".json":
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                result["schema"] = parsed.get("schema") or parsed.get("$schema")
        return result
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return {"path": relative, "status": "invalid", "error": type(error).__name__}


def observe_local_repository(repo: Path, org: dict[str, Any], max_tickets: int) -> dict[str, Any]:
    origin = _git(repo, "remote", "get-url", "origin", check=False)
    full_name = _origin_full_name(origin) or f"{org['id']}/{repo.name}"
    head = _git(repo, "rev-parse", "HEAD", check=False) or None
    branch = _git(repo, "symbolic-ref", "--short", "HEAD", check=False) or None
    status = _git(repo, "status", "--porcelain=v1", check=False)
    upstream = _git(repo, "rev-parse", "--abbrev-ref", "@{upstream}", check=False) or None
    ahead = behind = 0
    upstream_state = "none"
    if upstream:
        upstream_state = "present"
        counts = _git(repo, "rev-list", "--left-right", "--count", f"HEAD...{upstream}", check=False)
        if counts:
            ahead, behind = (int(item) for item in counts.split())
    elif branch and _git(repo, "config", f"branch.{branch}.remote", check=False):
        upstream_state = "gone"

    carriers = [item for relative in org["ssotCarriers"] if (item := _carrier(repo, relative))]
    manifest_path = repo / ".governance/manifest.json"
    manifest: dict[str, Any] = {}
    if manifest_path.is_file():
        try:
            candidate = json.loads(_read_bytes(manifest_path))
            manifest = candidate if isinstance(candidate, dict) else {}
        except (OSError, ValueError, json.JSONDecodeError):
            pass
    version = None
    if (repo / "VERSION").is_file():
        version = _read_bytes(repo / "VERSION", 128).decode("utf-8", "replace").strip()
    return {
        "id": full_name,
        "organization": org["id"],
        "declaredRole": org["role"],
        "local": True,
        "remote": False,
        "locator": f"repo://workspace/{full_name}",
        "git": {
            "head": head,
            "branch": branch,
            "dirty": bool(status),
            "changedPathCount": len(status.splitlines()) if status else 0,
            "upstream": upstream,
            "upstreamState": upstream_state,
            "ahead": ahead,
            "behind": behind,
        },
        "declarations": {
            "version": version,
            "governance": bool(manifest),
            "governanceSchema": manifest.get("schema"),
            "standard": manifest.get("standard"),
            "stacks": manifest.get("stacks", []),
            "repository": manifest.get("repository"),
        },
        "ssotCarriers": carriers,
        "tickets": _ticket_summary(repo, max_tickets),
    }


def _workspace_root(repository_root: Path) -> Path:
    common = _git(repository_root, "rev-parse", "--path-format=absolute", "--git-common-dir", check=False)
    common_path = Path(common) if common else repository_root / ".git"
    primary_repository = common_path.parent if common_path.name == ".git" else repository_root
    return primary_repository.parent.resolve()


def _resolve_root(repository_root: Path, source: dict[str, str]) -> Path:
    configured = os.environ.get(source["env"], source["default"])
    if configured.startswith("workspace://"):
        organization = configured.removeprefix("workspace://")
        workspace = _workspace_root(repository_root)
        return workspace if workspace.name == organization else workspace.parent / organization
    path = Path(configured)
    return path.resolve() if path.is_absolute() else (repository_root / path).resolve()


def discover_local(config: dict[str, Any], repository_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    receipts: list[dict[str, Any]] = []
    repositories: list[dict[str, Any]] = []
    remaining = int(config["maxRepositories"])
    for org in config["organizations"]:
        root = _resolve_root(repository_root, org["localRoot"])
        receipt = {"id": org["id"], "kind": "organization-local", "required": org["required"]}
        if not root.is_dir():
            receipt.update(status="unavailable", error="root-not-found", repositoryCount=0)
            receipts.append(receipt)
            continue
        candidates = sorted(
            path for path in root.iterdir()
            if path.is_dir() and not path.is_symlink() and (path / ".git").exists()
        )
        selected = candidates[:remaining]
        errors = 0
        for repo in selected:
            try:
                repositories.append(observe_local_repository(repo, org, int(config["maxTicketsPerRepository"])))
            except (OSError, RuntimeError, ValueError):
                errors += 1
                repositories.append(
                    {
                        "id": f"{org['id']}/{repo.name}",
                        "organization": org["id"],
                        "declaredRole": org["role"],
                        "local": True,
                        "remote": False,
                        "locator": f"repo://workspace/{org['id']}/{repo.name}",
                        "sourceObservation": {"status": "unavailable", "error": "repository-observation-failed"},
                    }
                )
        remaining -= len(selected)
        receipt.update(
            status="healthy" if errors == 0 else "partial",
            repositoryCount=len(selected),
            errorCount=errors,
            truncated=len(candidates) > len(selected),
        )
        receipts.append(receipt)
    return receipts, repositories


def _remote_repositories_with_gh(org_id: str) -> list[dict[str, Any]]:
    result = subprocess.run(
        [
            "gh", "api", "--paginate", f"orgs/{org_id}/repos?per_page=100&type=all",
            "--jq", ".[] | {full_name,archived,private,default_branch,updated_at,pushed_at}",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode:
        raise RuntimeError("github-cli observation failed")
    return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]


def _remote_repositories_with_http(org_id: str) -> list[dict[str, Any]]:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repositories: list[dict[str, Any]] = []
    for page in range(1, 11):
        request = urllib.request.Request(
            f"https://api.github.com/orgs/{org_id}/repos?per_page=100&type=all&page={page}",
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "twin-subactor/0.1",
                **({"Authorization": f"Bearer {token}"} if token else {}),
            },
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            page_items = json.load(response)
        repositories.extend(page_items)
        if len(page_items) < 100:
            break
    return repositories


def discover_remote(config: dict[str, Any], offline: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    receipts: list[dict[str, Any]] = []
    repositories: list[dict[str, Any]] = []
    for org in config["organizations"]:
        receipt = {"id": org["id"], "kind": "organization-remote", "required": org.get("remoteRequired", False)}
        if offline:
            receipt.update(status="disabled", repositoryCount=0)
            receipts.append(receipt)
            continue
        try:
            items = _remote_repositories_with_gh(org["id"]) if shutil.which("gh") else _remote_repositories_with_http(org["id"])
            for item in items[: int(config["maxRepositories"])]:
                repositories.append(
                    {
                        "id": item["full_name"],
                        "organization": org["id"],
                        "declaredRole": org["role"],
                        "local": False,
                        "remote": True,
                        "remoteState": {
                            "archived": bool(item.get("archived")),
                            "private": bool(item.get("private")),
                            "defaultBranch": item.get("default_branch"),
                            "updatedAt": item.get("updated_at"),
                            "pushedAt": item.get("pushed_at"),
                        },
                    }
                )
            receipt.update(status="healthy", repositoryCount=len(items), truncated=len(items) > int(config["maxRepositories"]))
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError, urllib.error.URLError):
            receipt.update(status="unavailable", error="remote-observation-failed", repositoryCount=0)
        receipts.append(receipt)
    return receipts, repositories


def _bounded_summary(identifier: str, body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        return {"schema": None, "shape": type(body).__name__}
    summary: dict[str, Any] = {"schema": body.get("schema")}
    if isinstance(body.get("stats"), dict):
        summary["stats"] = body["stats"]
    if identifier == "system-context":
        for key in ("actors", "services", "connectors", "routes", "tickets", "artifacts", "sprints", "errors"):
            if isinstance(body.get(key), list):
                summary[f"{key}Count"] = len(body[key])
        if isinstance(body.get("autonomy"), dict):
            summary["autonomy"] = body["autonomy"]
    if identifier == "system-state":
        for key in ("registry", "stateVariables", "state_variables", "statePolicies", "state_policies"):
            value = body.get(key)
            if isinstance(value, (list, dict)):
                summary[f"{key}Count"] = len(value)
            elif value is None:
                summary[f"{key}Count"] = 0
    return summary


def observe_control(config: dict[str, Any], offline: bool) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    control = config["control"]
    if offline:
        return [{"id": "control", "kind": "control-read-model", "required": control["required"], "status": "disabled"}], {}
    base_url = os.environ.get(control["baseUrlEnv"], control["defaultBaseUrl"]).rstrip("/")
    token = os.environ.get(control["tokenEnv"], "").strip()
    projections: dict[str, Any] = {}
    endpoint_receipts: list[dict[str, Any]] = []
    for endpoint in control["endpoints"]:
        try:
            request = urllib.request.Request(
                base_url + endpoint["path"],
                headers={"Accept": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})},
            )
            with urllib.request.urlopen(request, timeout=control["timeoutSeconds"]) as response:
                raw = response.read(int(control["maxResponseBytes"]) + 1)
            if len(raw) > int(control["maxResponseBytes"]):
                raise ValueError("response-too-large")
            body = json.loads(raw)
            projections[endpoint["id"]] = _bounded_summary(endpoint["id"], body)
            endpoint_receipts.append({"id": endpoint["id"], "status": "healthy", "digest": "sha256:" + hashlib.sha256(raw).hexdigest()})
        except (OSError, ValueError, json.JSONDecodeError, urllib.error.URLError):
            endpoint_receipts.append({"id": endpoint["id"], "status": "unavailable", "error": "read-model-unavailable"})
    statuses = {item["status"] for item in endpoint_receipts}
    status = "healthy" if statuses == {"healthy"} else "unavailable" if statuses == {"unavailable"} else "partial"
    return [
        {
            "id": "control",
            "kind": "control-read-model",
            "required": control["required"],
            "status": status,
            "endpoints": endpoint_receipts,
        }
    ], projections


def load_config(path: Path) -> dict[str, Any]:
    value = json.loads(_read_bytes(path))
    if value.get("schema") != "twin-subactor.sources/v1":
        raise ValueError("unsupported sources schema")
    for org in value.get("organizations", []):
        if not ORG_RE.fullmatch(org.get("id", "")):
            raise ValueError("invalid organization id")
    return value
