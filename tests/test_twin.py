from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from twin_subactor.diagnosis import diagnose, next_actions
from twin_subactor.model import _merge_repositories, build_snapshot
from twin_subactor.sources import digest, discover_local, load_config, observe_local_repository


class TwinTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def make_repo(self, name: str, *, dirty: bool = False, governed: bool = True) -> Path:
        repo = self.root / name
        repo.mkdir()
        subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "Twin Test"], check=True)
        (repo / "README.md").write_text("# fixture\n")
        if governed:
            (repo / ".governance").mkdir()
            (repo / ".governance/manifest.json").write_text(json.dumps({"schema": "new-project.governance/v2", "standard": {"id": "wellmanifest/new-project", "version": "0.18.1"}}))
        subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
        if governed:
            subprocess.run(["git", "-C", str(repo), "add", ".governance/manifest.json"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "fixture"], check=True, capture_output=True)
        if dirty:
            (repo / "README.md").write_text("changed\n")
        return repo

    def test_local_observation_uses_declared_role_and_reports_dirty(self) -> None:
        repo = self.make_repo("alpha", dirty=True)
        org = {"id": "subactor", "role": "declared-test-role", "ssotCarriers": [".governance/manifest.json"]}
        observed = observe_local_repository(repo, org, 10)
        self.assertEqual(observed["declaredRole"], "declared-test-role")
        self.assertTrue(observed["git"]["dirty"])
        self.assertTrue(observed["declarations"]["governance"])

    def test_discovery_marks_missing_required_root_unavailable(self) -> None:
        config = {
            "maxRepositories": 10,
            "maxTicketsPerRepository": 10,
            "organizations": [
                {"id": "subactor", "required": True, "role": "runtime", "localRoot": {"env": "TEST_TWIN_ROOT", "default": "missing"}, "ssotCarriers": []}
            ],
        }
        with mock.patch.dict(os.environ, {"TEST_TWIN_ROOT": str(self.root / "absent")}, clear=False):
            sources, repositories = discover_local(config, self.root)
        self.assertEqual(sources[0]["status"], "unavailable")
        self.assertEqual(repositories, [])

    def test_findings_are_deduplicated_and_handoffs_require_authority(self) -> None:
        snapshot = {
            "snapshotDigest": digest({"snapshot": 1}),
            "sources": [{"id": "subactor", "kind": "organization-local", "required": True, "status": "unavailable", "error": "root-not-found"}],
            "repositories": [],
            "control": {},
        }
        config = {
            "expectedGovernanceStandard": "0.18.1",
            "decision": {
                "policyRef": "priority://test/v1",
                "lifecycleRef": "lifecycle://test/v1",
                "doctorSkillRef": "skills://doctor/v1",
                "repairProcessRef": "skills://repair/v1",
                "validatorProcessRef": "skills://validator/v1",
            },
        }
        snapshot["findings"] = diagnose(snapshot, config)
        first = next_actions(snapshot, config)
        second = next_actions(snapshot, config)
        self.assertEqual(first, second)
        self.assertEqual(first[0]["authority"], "external-digest-bound-grant-required-for-mutation")
        self.assertEqual(first[0]["pipeline"][1]["state"], "not-authorized")

    def test_remote_and_local_observations_merge_without_name_inference(self) -> None:
        merged = _merge_repositories(
            [{"id": "subactor/alpha", "local": True, "declaredRole": "runtime", "git": {"head": "abc"}}],
            [{"id": "subactor/alpha", "remote": True, "declaredRole": "runtime", "remoteState": {"archived": False}}],
        )
        self.assertEqual(len(merged), 1)
        self.assertTrue(merged[0]["local"])
        self.assertTrue(merged[0]["remote"])

    def test_snapshot_digest_ignores_capture_time_but_binds_content(self) -> None:
        config_path = self.root / "config/sources.json"
        config_path.parent.mkdir()
        config_path.write_text(json.dumps({"schema": "twin-subactor.sources/v1", "organizations": [], "decision": {}}))
        with (
            mock.patch("twin_subactor.model.discover_local", return_value=([], [])),
            mock.patch("twin_subactor.model.discover_remote", return_value=([], [])),
            mock.patch("twin_subactor.model.observe_control", return_value=([], {})),
            mock.patch("twin_subactor.model.diagnose", return_value=[]),
            mock.patch("twin_subactor.model.next_actions", return_value=[]),
        ):
            first = build_snapshot(config_path, offline=True)
            second = build_snapshot(config_path, offline=True)
        self.assertEqual(first["snapshotDigest"], second["snapshotDigest"])

    def test_config_uses_closed_organization_identifiers(self) -> None:
        path = self.root / "sources.json"
        path.write_text(json.dumps({"schema": "twin-subactor.sources/v1", "organizations": [{"id": "bad/name"}]}))
        with self.assertRaises(ValueError):
            load_config(path)


if __name__ == "__main__":
    unittest.main()
