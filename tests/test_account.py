from __future__ import annotations

import contextlib
import io
import json
import sqlite3
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from twin_subactor.account import (
    PROFILE_ID,
    build_account_projection,
    observe_account_api,
    query_account_projection,
)
from twin_subactor.cli import main
from twin_subactor.service import SnapshotCache, make_handler


class JsonResponse:
    def __init__(self, value: object) -> None:
        self.raw = json.dumps(value).encode()

    def __enter__(self) -> "JsonResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, maximum: int = -1) -> bytes:
        return self.raw if maximum < 0 else self.raw[:maximum]


class AccountTwinTests(unittest.TestCase):
    def fixture(self, root: Path) -> tuple[Path, Path]:
        workspace = root / "workspace" / "subactor"
        active = workspace / "c2004-mask-services"
        legacy = workspace / "projekty-legacy-20260831" / "wydruk-subactor-com"
        (active / ".git").mkdir(parents=True)
        legacy.mkdir(parents=True)
        (active / "project.manifest.json").write_text(
            json.dumps(
                {
                    "schema": "subactor.projects/v1",
                    "projects": [
                        {
                            "id": "c2004-mask-services",
                            "company": "Maskservice",
                            "domain": "c2004.mask.services",
                            "status": "blocked",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (legacy / "project.manifest.json").write_text(
            json.dumps(
                {
                    "schema": "subactor.projects/v1",
                    "projects": [
                        {
                            "id": "wydruk-subactor-com",
                            "company": "Subactor",
                            "domain": "wydruk.subactor.com",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        repository = root / "twin-subactor"
        config_path = repository / "config" / "sources.json"
        config_path.parent.mkdir(parents=True)
        config_path.write_text(
            json.dumps(
                {
                    "schema": "twin-subactor.sources/v1",
                    "maxRepositories": 20,
                    "maxTicketsPerRepository": 20,
                    "expectedGovernanceStandard": "0.18.1",
                    "organizations": [
                        {
                            "id": "subactor",
                            "required": True,
                            "governanceExpected": True,
                            "role": "runtime-and-product-source",
                            "localRoot": {"env": "ACCOUNT_TEST_ROOT", "default": str(workspace)},
                            "ssotCarriers": ["project/TICKETS.md", "VERSION"],
                        }
                    ],
                    "control": {
                        "required": True,
                        "baseUrlEnv": "ACCOUNT_TEST_CONTROL_URL",
                        "defaultBaseUrl": "http://127.0.0.1:9",
                        "tokenEnv": "ACCOUNT_TEST_CONTROL_TOKEN",
                        "timeoutSeconds": 0.1,
                        "maxResponseBytes": 1024,
                        "endpoints": [],
                    },
                    "accountTwin": {
                        "schema": "twin-subactor.account-sources/v1",
                        "profileId": PROFILE_ID,
                        "accountId": "subactor",
                        "maxProjectManifests": 20,
                        "apiSources": [
                            {
                                "id": "test-tickets",
                                "entityType": "ticket",
                                "required": True,
                                "baseUrlEnv": "ACCOUNT_TEST_PLANFILE_URL",
                                "defaultBaseUrl": "http://127.0.0.1:9",
                                "tokenEnv": "ACCOUNT_TEST_TOKEN",
                                "path": "/tickets",
                                "itemKeys": ["tickets"],
                                "maxRecords": 20,
                            }
                        ],
                    },
                    "decision": {
                        "policyRef": "priority://test",
                        "lifecycleRef": "lifecycle://test",
                        "doctorSkillRef": "skills://doctor",
                        "repairProcessRef": "skills://repair",
                        "validatorProcessRef": "skills://validator",
                    },
                }
            ),
            encoding="utf-8",
        )
        return config_path, workspace

    def test_offline_rebuild_discovers_active_and_legacy_projects(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, _workspace = self.fixture(root)
            database = root / "state" / "account.sqlite3"
            summary = build_account_projection(config, database, offline=True)

            self.assertEqual(summary["profileId"], PROFILE_ID)
            self.assertFalse(summary["complete"])
            self.assertEqual(summary["counts"]["project"], 2)
            projects = query_account_projection(database, "projects", limit=20)["items"]
            by_id = {item["id"]: item for item in projects}
            self.assertEqual(
                by_id["c2004-mask-services"]["payload"]["_twin"]["locationState"],
                "active-repository",
            )
            self.assertEqual(
                by_id["wydruk-subactor-com"]["payload"]["_twin"]["locationState"],
                "legacy-tree",
            )
            self.assertTrue(by_id["c2004-mask-services"]["localPath"].endswith("/c2004-mask-services"))
            sources = query_account_projection(database, "sources", limit=50)["items"]
            self.assertIn("disabled", {item["status"] for item in sources})
            with contextlib.closing(sqlite3.connect(database)) as connection:
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 1)

    def test_managed_site_registry_preserves_missing_declared_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, workspace = self.fixture(root)
            registry = workspace / "platform" / "config" / "site-resources.json"
            registry.parent.mkdir(parents=True)
            missing = workspace / "projekty" / "wydruk-subactor-com" / "site"
            registry.write_text(
                json.dumps(
                    {
                        "resources": [
                            {
                                "id": "workspace:wydruk-subactor-com",
                                "domain": "wydruk.subactor.com",
                                "path": str(missing),
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            document = json.loads(config.read_text(encoding="utf-8"))
            document["accountTwin"]["localSources"] = [
                {
                    "id": "site-resources",
                    "entityType": "project",
                    "organizationId": "subactor",
                    "required": True,
                    "relativePath": "platform/config/site-resources.json",
                    "itemKeys": ["resources"],
                    "idPrefixToStrip": "workspace:",
                    "declaredPathField": "path",
                }
            ]
            config.write_text(json.dumps(document), encoding="utf-8")
            database = root / "account.sqlite3"
            build_account_projection(config, database, offline=True)

            observed = query_account_projection(
                database, "projects", filters={"source": "site-resources"}, limit=20
            )["items"]
            self.assertEqual(observed[0]["id"], "wydruk-subactor-com")
            self.assertIsNone(observed[0]["localPath"])
            self.assertEqual(observed[0]["payload"]["_twin"]["locationState"], "declared-path-missing")

    def test_api_observation_redacts_secret_shaped_fields(self) -> None:
        source = {
            "id": "tickets",
            "entityType": "ticket",
            "required": True,
            "baseUrlEnv": "ACCOUNT_TEST_API",
            "defaultBaseUrl": "http://api.test",
            "tokenEnv": "ACCOUNT_TEST_TOKEN",
            "path": "/tickets",
            "itemKeys": ["tickets"],
            "maxRecords": 10,
        }
        payload = {
            "tickets": [
                {
                    "id": "PLF-1",
                    "name": "Repair route",
                    "api_token": "must-not-persist",
                    "nested": {"authorization": "must-not-persist"},
                }
            ]
        }
        with mock.patch("twin_subactor.account.urllib.request.urlopen", return_value=JsonResponse(payload)):
            receipt, entities = observe_account_api("subactor", source, offline=False)
        self.assertEqual(receipt["status"], "healthy")
        serialized = json.dumps(entities)
        self.assertNotIn("must-not-persist", serialized)
        self.assertEqual(entities[0]["payload"]["api_token"], "[redacted]")

    def test_failed_candidate_preserves_last_valid_projection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, _workspace = self.fixture(root)
            database = root / "account.sqlite3"
            first = build_account_projection(config, database, offline=True)
            with mock.patch("twin_subactor.account._write_database", side_effect=RuntimeError("candidate failed")):
                with self.assertRaisesRegex(RuntimeError, "candidate failed"):
                    build_account_projection(config, database, offline=True)
            self.assertEqual(query_account_projection(database, "summary")["projectionDigest"], first["projectionDigest"])
            self.assertEqual(list(database.parent.glob(".*.candidate")), [])

    def test_cli_and_http_read_the_same_projection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, _workspace = self.fixture(root)
            database = root / "account.sqlite3"
            build_account_projection(config, database, offline=True)

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = main(["--config", str(config), "--account-db", str(database), "account-query", "summary"])
            self.assertEqual(code, 0)
            cli_value = json.loads(stdout.getvalue())

            cache = SnapshotCache(lambda: {"snapshotDigest": "unused"})
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(cache, database))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{server.server_port}/v1/account/summary", timeout=2
                ) as response:
                    http_value = json.load(response)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
            self.assertEqual(http_value["projectionDigest"], cli_value["projectionDigest"])

    def test_research_matrix_joins_project_ticket_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, _workspace = self.fixture(root)
            database = root / "account.sqlite3"
            build_account_projection(config, database, offline=True)
            matrix = query_account_projection(database, "combinations", limit=20)["items"]
            self.assertEqual({item["projectId"] for item in matrix}, {"c2004-mask-services", "wydruk-subactor-com"})
            self.assertTrue(all(item["ticketCount"] == 0 for item in matrix))


if __name__ == "__main__":
    unittest.main()
