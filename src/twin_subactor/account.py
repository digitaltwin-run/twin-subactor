from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .model import build_snapshot
from .sources import canonical_bytes, digest, load_config, resolve_organization_root

PROFILE_ID = "twin-subactor-account"
PROJECTION_SCHEMA = "subactor.account-twin.projection/v1"
DATABASE_SCHEMA_VERSION = 1
REDACTED = "[redacted]"
SECRET_KEY = re.compile(
    r"authorization|cookie|credential|password|secret|token|api[_-]?key",
    re.IGNORECASE,
)
QUERY_RESOURCES = {
    "organizations",
    "projects",
    "tickets",
    "repositories",
    "project-reconciliations",
    "deployments",
    "entities",
    "sources",
    "combinations",
    "summary",
}
ENTITY_VIEW_TYPES = {
    "organizations": "organization",
    "projects": "project",
    "tickets": "ticket",
    "repositories": "repository",
    "project-reconciliations": "project-reconciliation",
    "deployments": "deployment-binding",
}


def default_database() -> Path:
    configured = os.environ.get("TWIN_SUBACTOR_ACCOUNT_DB", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    state_root = os.environ.get("XDG_STATE_HOME", "").strip()
    base = Path(state_root).expanduser() if state_root else Path.home() / ".local" / "state"
    return (base / "twin-subactor" / "twin-subactor-account.sqlite3").resolve()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json(value: Any) -> str:
    return canonical_bytes(value).decode("utf-8")


def _read_bounded(path: Path, maximum: int) -> bytes:
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError("local-source-too-large")
    return raw


def _redact(value: Any) -> Any:
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            name = str(key)
            reference = name.lower().endswith(("_ref", "_refs", "_handle", "_handles"))
            result[name] = REDACTED if SECRET_KEY.search(name) and not reference else _redact(item)
        return result
    return value


def _field(value: dict[str, Any], *candidates: str) -> Any:
    for candidate in candidates:
        current: Any = value
        for part in candidate.split("."):
            if not isinstance(current, dict) or part not in current:
                current = None
                break
            current = current[part]
        if current not in (None, "") and not isinstance(current, (dict, list)):
            return current
    return None


def _string(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _entity(
    account_id: str,
    entity_type: str,
    source_id: str,
    payload: dict[str, Any],
    *,
    fallback_id: str = "",
) -> dict[str, Any]:
    safe = _redact(payload)
    identifiers = {
        "organization": ("id", "organization_id", "slug", "name"),
        "project": ("id", "project_id", "slug", "domain", "name"),
        "ticket": ("id", "ticket_id", "key", "name", "title"),
        "repository": ("id", "full_name", "name"),
        "project-reconciliation": ("project_id", "id", "domain"),
        "deployment-binding": ("id", "deployment_id", "source_ref"),
    }
    external_id = _string(_field(safe, *identifiers.get(entity_type, ("id", "name")))) or fallback_id
    if not external_id:
        external_id = hashlib.sha256(canonical_bytes(safe)).hexdigest()[:24]
    canonical_id = external_id.strip().lower()
    organization_id = _string(
        _field(safe, "organization_id", "organization.id", "organization", "org_id", "org")
    )
    project_id = _string(_field(safe, "project_id", "project.id", "project"))
    if entity_type == "project":
        project_id = external_id
    name = _string(_field(safe, "name", "title", "display_name", "domain"))
    status = _string(_field(safe, "status", "state", "execution.state"))
    domain = _string(_field(safe, "domain", "hostname", "site.domain"))
    local_path = _string(_field(safe, "_twin.localPath", "local_path", "localPath"))
    return {
        "account_id": account_id,
        "entity_type": entity_type,
        "source_id": source_id,
        "external_id": external_id,
        "canonical_id": canonical_id,
        "organization_id": organization_id,
        "project_id": project_id,
        "name": name,
        "status": status,
        "domain": domain,
        "local_path": local_path,
        "payload": safe,
        "payload_digest": digest(safe),
    }


def _extract_items(body: Any, keys: Iterable[str]) -> list[dict[str, Any]]:
    if isinstance(body, list):
        return [item for item in body if isinstance(item, dict)]
    if not isinstance(body, dict):
        return []
    for key in keys:
        current: Any = body
        for part in key.split("."):
            current = current.get(part) if isinstance(current, dict) else None
        if isinstance(current, list):
            return [item for item in current if isinstance(item, dict)]
    return []


def _read_api_page(source: dict[str, Any], offset: int, page_size: int) -> tuple[Any, bytes]:
    base_url = os.environ.get(source["baseUrlEnv"], source["defaultBaseUrl"]).rstrip("/")
    parsed = urllib.parse.urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("api-base-url-invalid")
    path = str(source["path"]).format(offset=offset, limit=page_size)
    authorization = os.environ.get(source.get("tokenEnv", ""), "").strip()
    request = urllib.request.Request(
        base_url + path,
        headers={
            "Accept": "application/json",
            "User-Agent": "twin-subactor-account/0.2",
            **({"Authorization": f"Bearer {authorization}"} if authorization else {}),
        },
    )
    maximum = int(source.get("maxResponseBytes", 8_388_608))
    with urllib.request.urlopen(request, timeout=float(source.get("timeoutSeconds", 10))) as response:
        raw = response.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError("api-response-too-large")
    return json.loads(raw), raw


def observe_account_api(
    account_id: str, source: dict[str, Any], *, offline: bool
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    receipt: dict[str, Any] = {
        "id": source["id"],
        "kind": "account-api",
        "required": bool(source.get("required", False)),
    }
    if offline:
        return {**receipt, "status": "disabled", "itemCount": 0}, []

    page_size = max(1, min(int(source.get("pageSize", source.get("maxRecords", 1000))), 5000))
    maximum = max(1, min(int(source.get("maxRecords", 1000)), 100_000))
    paginated = bool(source.get("paginated", False))
    items: list[dict[str, Any]] = []
    page_digests: list[str] = []
    try:
        while len(items) < maximum:
            requested = min(page_size, maximum - len(items))
            try:
                body, raw = _read_api_page(source, len(items), requested)
            except urllib.error.HTTPError as error:
                if paginated and error.code == 413 and requested > 1:
                    page_size = max(1, requested // 2)
                    continue
                raise
            except ValueError as error:
                if paginated and str(error) == "api-response-too-large" and requested > 1:
                    page_size = max(1, requested // 2)
                    continue
                raise
            page = _extract_items(body, source.get("itemKeys", ["rows", "items"]))
            page_digests.append(hashlib.sha256(raw).hexdigest())
            items.extend(page)
            if not paginated or len(page) < requested:
                break
            if not page:
                break
        truncated = len(items) >= maximum
        entities = [
            _entity(account_id, source["entityType"], source["id"], item)
            for item in items[:maximum]
        ]
        return {
            **receipt,
            "status": "partial" if truncated else "healthy",
            "itemCount": len(entities),
            "truncated": truncated,
            "digest": digest(page_digests),
        }, entities
    except (OSError, ValueError, json.JSONDecodeError, urllib.error.URLError):
        return {**receipt, "status": "unavailable", "itemCount": 0, "error": "api-observation-failed"}, []


def _project_manifest_paths(root: Path, maximum: int) -> list[Path]:
    paths: set[Path] = set()
    for pattern in ("project.manifest.json", "*/project.manifest.json", "*/*/project.manifest.json"):
        try:
            candidates = list(root.glob(pattern))
        except OSError:
            continue
        for candidate in candidates:
            if len(paths) >= maximum:
                break
            try:
                relative = candidate.relative_to(root)
                parents = [root / Path(*relative.parts[:index]) for index in range(1, len(relative.parts))]
                if candidate.is_file() and not candidate.is_symlink() and not any(parent.is_symlink() for parent in parents):
                    paths.add(candidate.resolve())
            except (OSError, ValueError):
                continue
    return sorted(paths)[:maximum]


def _location_state(root: Path, manifest: Path) -> str:
    relative = manifest.parent.relative_to(root)
    if relative.parts and "legacy" in relative.parts[0].lower():
        return "legacy-tree"
    current = manifest.parent
    while current != root and root in current.parents:
        if (current / ".git").exists():
            return "active-repository" if current == manifest.parent else "active-repository-subpath"
        current = current.parent
    return "workspace-tree"


def observe_local_documents(
    account_id: str,
    config: dict[str, Any],
    roots: dict[str, Path],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    receipts: list[dict[str, Any]] = []
    entities: list[dict[str, Any]] = []
    for source in config.get("accountTwin", {}).get("localSources", []):
        source_id = str(source["id"])
        organization_id = str(source["organizationId"])
        root = roots.get(organization_id)
        receipt: dict[str, Any] = {
            "id": source_id,
            "kind": "account-local-document",
            "required": bool(source.get("required", False)),
            "itemCount": 0,
        }
        if root is None:
            receipts.append({**receipt, "status": "unavailable", "error": "organization-root-unknown"})
            continue
        path = (root / str(source["relativePath"])).resolve()
        try:
            path.relative_to(root.resolve())
            maximum = int(source.get("maxResponseBytes", 8_388_608))
            raw = _read_bounded(path, maximum)
            document = json.loads(raw)
            items = _extract_items(document, source.get("itemKeys", ["items", "rows"]))
            maximum_records = max(1, min(int(source.get("maxRecords", 10_000)), 100_000))
            truncated = len(items) > maximum_records
            for item in items[:maximum_records]:
                payload = dict(item)
                original_id = _string(payload.get("id"))
                prefix = str(source.get("idPrefixToStrip", ""))
                if original_id and prefix and original_id.startswith(prefix):
                    payload["source_ref"] = original_id
                    payload["id"] = original_id.removeprefix(prefix)
                declared_path = _string(_field(payload, str(source.get("declaredPathField", "path"))))
                if declared_path:
                    declared = Path(declared_path).expanduser()
                    exists = declared.exists()
                    payload["_twin"] = {
                        "declaredPath": declared_path,
                        "declaredPathExists": exists,
                        "locationState": "declared-path-present" if exists else "declared-path-missing",
                        **({"localPath": str(declared.resolve())} if exists else {}),
                    }
                entity = _entity(account_id, source["entityType"], source_id, payload)
                entity["organization_id"] = organization_id
                entities.append(entity)
            receipts.append(
                {
                    **receipt,
                    "status": "partial" if truncated else "healthy",
                    "itemCount": min(len(items), maximum_records),
                    "truncated": truncated,
                    "digest": "sha256:" + hashlib.sha256(raw).hexdigest(),
                    "artifact": str(source["relativePath"]),
                }
            )
        except (OSError, ValueError, json.JSONDecodeError):
            receipts.append({**receipt, "status": "unavailable", "error": "local-document-unavailable"})
    return receipts, entities


def observe_local_account(
    account_id: str,
    config: dict[str, Any],
    repository_root: Path,
    ecosystem_snapshot: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    entities: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []
    roots: dict[str, Path] = {}
    local_paths: dict[str, str] = {}
    for organization in config["organizations"]:
        root = resolve_organization_root(repository_root, organization["localRoot"])
        roots[organization["id"]] = root
        entities.append(
            _entity(
                account_id,
                "organization",
                "configured-organizations",
                {
                    "id": organization["id"],
                    "name": organization["id"],
                    "status": "configured",
                    "role": organization["role"],
                    "required": organization["required"],
                    "_twin": {"localPath": str(root)},
                },
            )
        )
        if root.is_dir():
            try:
                candidates = list(root.iterdir())
            except OSError:
                candidates = []
            for candidate in candidates:
                try:
                    if candidate.is_dir() and not candidate.is_symlink() and (candidate / ".git").exists():
                        local_paths[f"{organization['id']}/{candidate.name}"] = str(candidate.resolve())
                except OSError:
                    continue

    for repository in ecosystem_snapshot.get("repositories", []):
        if not isinstance(repository, dict):
            continue
        payload = dict(repository)
        path = local_paths.get(str(repository.get("id") or ""))
        if path:
            payload["_twin"] = {"localPath": path, "locationState": "active-repository"}
        entities.append(
            _entity(
                account_id,
                "repository",
                "ecosystem-repositories",
                payload,
                fallback_id=str(repository.get("id") or ""),
            )
        )

    maximum = int(config.get("accountTwin", {}).get("maxProjectManifests", 1000))
    for organization in config["organizations"]:
        root = roots[organization["id"]]
        source_id = f"local-project-manifests:{organization['id']}"
        receipt: dict[str, Any] = {
            "id": source_id,
            "kind": "account-local-manifests",
            "required": bool(organization["required"]),
            "itemCount": 0,
        }
        if not root.is_dir():
            receipts.append({**receipt, "status": "unavailable", "error": "root-not-found"})
            continue
        errors = 0
        manifest_digests: list[str] = []
        for manifest in _project_manifest_paths(root, maximum):
            try:
                raw = _read_bounded(manifest, 1_048_576)
                document = json.loads(raw)
                projects = document.get("projects", []) if isinstance(document, dict) else []
                if not isinstance(projects, list):
                    raise ValueError("project-manifest-projects-invalid")
                manifest_digests.append(hashlib.sha256(raw).hexdigest())
                for project in projects:
                    if not isinstance(project, dict):
                        errors += 1
                        continue
                    payload = {
                        **project,
                        "_twin": {
                            "organization": organization["id"],
                            "localPath": str(manifest.parent),
                            "manifestPath": str(manifest),
                            "locationState": _location_state(root, manifest),
                        },
                    }
                    entity = _entity(account_id, "project", source_id, payload)
                    entity["organization_id"] = organization["id"]
                    entities.append(entity)
                    receipt["itemCount"] += 1
            except (OSError, ValueError, json.JSONDecodeError):
                errors += 1
        receipts.append(
            {
                **receipt,
                "status": "healthy" if errors == 0 else "partial",
                "errorCount": errors,
                "digest": digest(manifest_digests),
            }
        )
    document_receipts, document_entities = observe_local_documents(account_id, config, roots)
    receipts.extend(document_receipts)
    entities.extend(document_entities)
    return receipts, entities


def _schema(connection: sqlite3.Connection) -> None:
    connection.execute(f"PRAGMA user_version = {DATABASE_SCHEMA_VERSION}")
    connection.executescript(
        """
        PRAGMA foreign_keys = ON;
        CREATE TABLE account_projection (
          account_id TEXT PRIMARY KEY,
          profile_id TEXT NOT NULL,
          schema_id TEXT NOT NULL,
          projection_digest TEXT NOT NULL,
          rebuilt_at TEXT NOT NULL,
          complete INTEGER NOT NULL CHECK (complete IN (0, 1))
        );
        CREATE TABLE source_observations (
          account_id TEXT NOT NULL,
          source_id TEXT NOT NULL,
          kind TEXT NOT NULL,
          required INTEGER NOT NULL CHECK (required IN (0, 1)),
          status TEXT NOT NULL,
          item_count INTEGER NOT NULL,
          source_digest TEXT,
          error TEXT,
          receipt_json TEXT NOT NULL,
          PRIMARY KEY (account_id, source_id),
          FOREIGN KEY (account_id) REFERENCES account_projection(account_id)
        );
        CREATE TABLE entities (
          account_id TEXT NOT NULL,
          entity_type TEXT NOT NULL,
          source_id TEXT NOT NULL,
          external_id TEXT NOT NULL,
          canonical_id TEXT NOT NULL,
          organization_id TEXT,
          project_id TEXT,
          name TEXT,
          status TEXT,
          domain TEXT,
          local_path TEXT,
          payload_digest TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          PRIMARY KEY (account_id, entity_type, source_id, external_id),
          FOREIGN KEY (account_id, source_id) REFERENCES source_observations(account_id, source_id)
        );
        CREATE INDEX entities_type_canonical ON entities(account_id, entity_type, canonical_id);
        CREATE INDEX entities_project ON entities(account_id, project_id);
        CREATE INDEX entities_organization ON entities(account_id, organization_id);
        CREATE VIEW organizations AS SELECT * FROM entities WHERE entity_type = 'organization';
        CREATE VIEW projects AS SELECT * FROM entities WHERE entity_type = 'project';
        CREATE VIEW tickets AS SELECT * FROM entities WHERE entity_type = 'ticket';
        CREATE VIEW repositories AS SELECT * FROM entities WHERE entity_type = 'repository';
        CREATE VIEW project_reconciliations AS SELECT * FROM entities WHERE entity_type = 'project-reconciliation';
        CREATE VIEW deployment_bindings AS SELECT * FROM entities WHERE entity_type = 'deployment-binding';
        """
    )


def _write_database(
    candidate: Path,
    account_id: str,
    projection_digest: str,
    rebuilt_at: str,
    complete: bool,
    receipts: list[dict[str, Any]],
    entities: list[dict[str, Any]],
) -> None:
    connection = sqlite3.connect(candidate)
    try:
        connection.execute("PRAGMA journal_mode = DELETE")
        connection.execute("PRAGMA synchronous = FULL")
        _schema(connection)
        connection.execute(
            "INSERT INTO account_projection VALUES (?, ?, ?, ?, ?, ?)",
            (account_id, PROFILE_ID, PROJECTION_SCHEMA, projection_digest, rebuilt_at, int(complete)),
        )
        for receipt in receipts:
            connection.execute(
                "INSERT INTO source_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    account_id,
                    receipt["id"],
                    receipt["kind"],
                    int(bool(receipt.get("required", False))),
                    receipt["status"],
                    int(receipt.get("itemCount", receipt.get("repositoryCount", 0))),
                    receipt.get("digest"),
                    receipt.get("error"),
                    _json(receipt),
                ),
            )
        unique: dict[tuple[str, str, str], dict[str, Any]] = {}
        for entity in entities:
            unique[(entity["entity_type"], entity["source_id"], entity["external_id"])] = entity
        for key in sorted(unique):
            entity = unique[key]
            connection.execute(
                """INSERT INTO entities VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    account_id,
                    entity["entity_type"],
                    entity["source_id"],
                    entity["external_id"],
                    entity["canonical_id"],
                    entity["organization_id"],
                    entity["project_id"],
                    entity["name"],
                    entity["status"],
                    entity["domain"],
                    entity["local_path"],
                    entity["payload_digest"],
                    _json(entity["payload"]),
                ),
            )
        connection.commit()
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("account-projection-integrity-check-failed")
    finally:
        connection.close()


def build_account_projection(
    config_path: Path,
    database_path: Path | None = None,
    *,
    offline: bool = False,
) -> dict[str, Any]:
    config_path = config_path.resolve()
    config = load_config(config_path)
    account = config.get("accountTwin")
    if not isinstance(account, dict) or account.get("profileId") != PROFILE_ID:
        raise ValueError("account-twin-profile-missing")
    account_id = str(account.get("accountId") or "").strip()
    if not account_id:
        raise ValueError("account-twin-account-id-missing")

    ecosystem = build_snapshot(config_path, offline=offline)
    local_receipts, entities = observe_local_account(account_id, config, config_path.parent.parent, ecosystem)
    receipts = [
        {
            **receipt,
            "id": f"ecosystem:{receipt['kind']}:{receipt['id']}",
            "itemCount": int(receipt.get("repositoryCount", 0)),
        }
        for receipt in ecosystem.get("sources", [])
    ]
    receipts.extend(local_receipts)
    receipts.append(
        {
            "id": "configured-organizations",
            "kind": "account-configuration",
            "required": True,
            "status": "healthy",
            "itemCount": len(config["organizations"]),
            "digest": digest(config["organizations"]),
        }
    )
    receipts.append(
        {
            "id": "ecosystem-repositories",
            "kind": "account-ecosystem-projection",
            "required": True,
            "status": "healthy",
            "itemCount": len(ecosystem.get("repositories", [])),
            "digest": ecosystem["snapshotDigest"],
        }
    )
    for source in account.get("apiSources", []):
        receipt, observed = observe_account_api(account_id, source, offline=offline)
        receipts.append(receipt)
        entities.extend(observed)

    receipt_by_id = {receipt["id"]: receipt for receipt in receipts}
    receipts = [receipt_by_id[key] for key in sorted(receipt_by_id)]
    entity_by_key = {
        (entity["entity_type"], entity["source_id"], entity["external_id"]): entity
        for entity in entities
    }
    entities = [entity_by_key[key] for key in sorted(entity_by_key)]
    semantic_entities = sorted(
        (
            {
                key: entity[key]
                for key in (
                    "entity_type",
                    "source_id",
                    "external_id",
                    "canonical_id",
                    "organization_id",
                    "project_id",
                    "payload_digest",
                )
            }
            for entity in entities
        ),
        key=lambda item: (item["entity_type"], item["source_id"], item["external_id"]),
    )
    projection_digest = digest(
        {
            "schema": PROJECTION_SCHEMA,
            "profileId": PROFILE_ID,
            "accountId": account_id,
            "sources": receipts,
            "entities": semantic_entities,
        }
    )
    rebuilt_at = _now()
    complete = all(
        receipt["status"] == "healthy"
        for receipt in receipts
        if bool(receipt.get("required", False))
    )
    target = (database_path or default_database()).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, candidate_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".candidate", dir=target.parent)
    os.close(descriptor)
    candidate = Path(candidate_name)
    try:
        _write_database(candidate, account_id, projection_digest, rebuilt_at, complete, receipts, entities)
        os.chmod(candidate, 0o600)
        os.replace(candidate, target)
        directory_descriptor = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        if candidate.exists():
            candidate.unlink()
    return query_account_projection(target, "summary")


def _connect_readonly(path: Path) -> sqlite3.Connection:
    target = path.expanduser().resolve()
    if not target.is_file():
        raise FileNotFoundError(target)
    connection = sqlite3.connect(f"{target.as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _decode_entity(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "type": row["entity_type"],
        "id": row["external_id"],
        "canonicalId": row["canonical_id"],
        "sourceId": row["source_id"],
        "organizationId": row["organization_id"],
        "projectId": row["project_id"],
        "name": row["name"],
        "status": row["status"],
        "domain": row["domain"],
        "localPath": row["local_path"],
        "payloadDigest": row["payload_digest"],
        "payload": json.loads(row["payload_json"]),
    }


def _summary(connection: sqlite3.Connection) -> dict[str, Any]:
    account = connection.execute("SELECT * FROM account_projection").fetchone()
    if account is None or account["schema_id"] != PROJECTION_SCHEMA:
        raise ValueError("account-projection-schema-invalid")
    counts = {
        row["entity_type"]: row["count"]
        for row in connection.execute(
            "SELECT entity_type, COUNT(*) AS count FROM entities GROUP BY entity_type ORDER BY entity_type"
        )
    }
    source_counts = {
        row["status"]: row["count"]
        for row in connection.execute(
            "SELECT status, COUNT(*) AS count FROM source_observations GROUP BY status ORDER BY status"
        )
    }
    return {
        "schema": PROJECTION_SCHEMA,
        "profileId": account["profile_id"],
        "accountId": account["account_id"],
        "projectionDigest": account["projection_digest"],
        "rebuiltAt": account["rebuilt_at"],
        "complete": bool(account["complete"]),
        "counts": counts,
        "sourceStatusCounts": source_counts,
    }


def _combinations(
    connection: sqlite3.Connection, filters: dict[str, str], limit: int, offset: int
) -> list[dict[str, Any]]:
    clauses = ["p.entity_type = 'project'"]
    values: list[Any] = []
    if filters.get("organization"):
        clauses.append("p.organization_id = ?")
        values.append(filters["organization"])
    if filters.get("project"):
        clauses.append("(p.canonical_id = ? OR p.external_id = ?)")
        values.extend([filters["project"].lower(), filters["project"]])
    if filters.get("status"):
        clauses.append("p.status = ?")
        values.append(filters["status"])
    query = f"""
      WITH project_rollup AS (
        SELECT account_id, canonical_id, MAX(external_id) AS project_id,
               MAX(organization_id) AS organization_id, MAX(name) AS name,
               MAX(status) AS status, MAX(domain) AS domain,
               MAX(local_path) AS local_path, COUNT(*) AS observation_count
        FROM entities p WHERE {' AND '.join(clauses)}
        GROUP BY account_id, canonical_id
      ), ticket_rollup AS (
        SELECT account_id, LOWER(COALESCE(project_id, '')) AS project_id,
               COUNT(*) AS ticket_count,
               SUM(CASE WHEN LOWER(COALESCE(status, '')) IN ('done','closed','completed','cancelled','rejected') THEN 0 ELSE 1 END) AS open_ticket_count
        FROM entities WHERE entity_type = 'ticket'
        GROUP BY account_id, LOWER(COALESCE(project_id, ''))
      )
      SELECT p.*, COALESCE(t.ticket_count, 0) AS ticket_count,
             COALESCE(t.open_ticket_count, 0) AS open_ticket_count
      FROM project_rollup p
      LEFT JOIN ticket_rollup t ON t.account_id = p.account_id AND t.project_id = p.canonical_id
      ORDER BY p.organization_id, p.project_id LIMIT ? OFFSET ?
    """
    values.extend([limit, offset])
    return [
        {
            "projectId": row["project_id"],
            "organizationId": row["organization_id"],
            "name": row["name"],
            "status": row["status"],
            "domain": row["domain"],
            "localPath": row["local_path"],
            "projectObservationCount": row["observation_count"],
            "ticketCount": row["ticket_count"],
            "openTicketCount": row["open_ticket_count"],
        }
        for row in connection.execute(query, values)
    ]


def query_account_projection(
    database_path: Path,
    resource: str,
    *,
    filters: dict[str, str] | None = None,
    limit: int = 200,
    offset: int = 0,
) -> dict[str, Any]:
    if resource not in QUERY_RESOURCES:
        raise ValueError("account-query-resource-invalid")
    limit = max(1, min(int(limit), 1000))
    offset = max(0, int(offset))
    selected_filters = {str(key): str(value) for key, value in (filters or {}).items() if value not in (None, "")}
    connection = _connect_readonly(database_path)
    try:
        summary = _summary(connection)
        if resource == "summary":
            return summary
        if resource == "sources":
            rows = connection.execute(
                "SELECT receipt_json FROM source_observations ORDER BY source_id LIMIT ? OFFSET ?",
                (limit, offset),
            )
            items = [json.loads(row["receipt_json"]) for row in rows]
        elif resource == "combinations":
            items = _combinations(connection, selected_filters, limit, offset)
        else:
            clauses = []
            values: list[Any] = []
            entity_type = ENTITY_VIEW_TYPES.get(resource)
            if entity_type:
                clauses.append("entity_type = ?")
                values.append(entity_type)
            if selected_filters.get("organization"):
                clauses.append("organization_id = ?")
                values.append(selected_filters["organization"])
            if selected_filters.get("project"):
                clauses.append("(project_id = ? OR canonical_id = ? OR external_id = ?)")
                values.extend(
                    [selected_filters["project"], selected_filters["project"].lower(), selected_filters["project"]]
                )
            if selected_filters.get("status"):
                clauses.append("status = ?")
                values.append(selected_filters["status"])
            if selected_filters.get("source"):
                clauses.append("source_id = ?")
                values.append(selected_filters["source"])
            if selected_filters.get("q"):
                clauses.append("LOWER(COALESCE(name, '') || ' ' || external_id || ' ' || COALESCE(domain, '')) LIKE ?")
                values.append(f"%{selected_filters['q'].lower()}%")
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            values.extend([limit, offset])
            rows = connection.execute(
                f"SELECT * FROM entities {where} ORDER BY entity_type, canonical_id, source_id LIMIT ? OFFSET ?",
                values,
            )
            items = [_decode_entity(row) for row in rows]
        return {
            "schema": "subactor.account-twin.query/v1",
            "profileId": summary["profileId"],
            "accountId": summary["accountId"],
            "projectionDigest": summary["projectionDigest"],
            "resource": resource,
            "offset": offset,
            "limit": limit,
            "items": items,
        }
    finally:
        connection.close()
