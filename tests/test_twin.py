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
from twin_subactor.sources import digest, discover_local, discover_remote, load_config, observe_local_repository


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

    def install_guard(self, repo: Path, *, runner: bool = True, track_runner: bool = True, fail_closed: bool = True, wire: bool = True) -> None:
        (repo / ".governance").mkdir(exist_ok=True)
        (repo / ".githooks").mkdir(exist_ok=True)
        (repo / "worktree-guard.yaml").write_text("schema: worktree-guard/v1\n")
        (repo / ".governance/worktree_overlap_check.py").write_text("# overlap\n")
        if runner:
            (repo / ".governance/worktree_guard.py").write_text("# runner\n")
        (repo / ".githooks/pre-commit").write_text(
            '#!/bin/sh\n"$(dirname "$0")/pre-commit-worktree-guard"\n' if wire else "#!/bin/sh\nexit 0\n"
        )
        fragment = "#!/bin/sh\necho 'worktree_guard.py is missing'\nexit 1\n" if fail_closed else "#!/bin/sh\nexit 0\n"
        (repo / ".githooks/pre-commit-worktree-guard").write_text(fragment)
        tracked = ["worktree-guard.yaml", ".governance/worktree_overlap_check.py", ".githooks/pre-commit", ".githooks/pre-commit-worktree-guard"]
        if runner and track_runner:
            tracked.append(".governance/worktree_guard.py")
        subprocess.run(["git", "-C", str(repo), "add", *tracked], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "guard"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "config", "core.hooksPath", ".githooks"], check=True)

    def test_local_observation_uses_declared_role_and_reports_dirty(self) -> None:
        repo = self.make_repo("alpha", dirty=True)
        org = {"id": "subactor", "role": "declared-test-role", "ssotCarriers": [".governance/manifest.json"]}
        observed = observe_local_repository(repo, org, 10)
        self.assertEqual(observed["declaredRole"], "declared-test-role")
        self.assertTrue(observed["git"]["dirty"])
        self.assertTrue(observed["declarations"]["governance"])

    def test_document_version_keeps_repository_and_extracts_semver(self) -> None:
        repo = self.make_repo("document-version")
        (repo / "VERSION").write_text(
            "# Version\n\n## Current Version\n\n`0.12.0`\n\n" + "bounded release notes\n" * 20
        )
        org = {"id": "subactor", "role": "runtime", "ssotCarriers": ["VERSION"]}
        observed = observe_local_repository(repo, org, 10)
        self.assertEqual(observed["declarations"]["version"], "0.12.0")
        self.assertEqual(observed["ssotCarriers"][0]["status"], "valid")
        self.assertIn("git", observed)

    def test_guard_projection_distinguishes_healthy_and_fail_open(self) -> None:
        healthy = self.make_repo("guard-healthy")
        self.install_guard(healthy)
        fail_open = self.make_repo("guard-fail-open")
        self.install_guard(fail_open, fail_closed=False)
        org = {"id": "subactor", "role": "runtime", "ssotCarriers": []}
        healthy_observation = observe_local_repository(healthy, org, 10)
        fail_open_observation = observe_local_repository(fail_open, org, 10)
        self.assertEqual(healthy_observation["governanceGuard"]["status"], "healthy")
        self.assertFalse(fail_open_observation["governanceGuard"]["failClosedWithoutRunner"])

        config = {"organizations": [{"id": "subactor", "governanceExpected": True}]}
        snapshot = {"sources": [], "repositories": [healthy_observation, fail_open_observation], "control": {}}
        codes = [item["code"] for item in diagnose(snapshot, config)]
        self.assertEqual(codes.count("TWIN-WORKTREE-GUARD-FAIL-OPEN"), 1)

    def test_guard_source_configuration_is_not_mistaken_for_an_adoption(self) -> None:
        repo = self.make_repo("guard-standard-source")
        (repo / "worktree-guard.yaml").write_text("schema: worktree-guard/v1\n")
        org = {"id": "wellmanifest", "role": "domain-standard-source", "ssotCarriers": []}
        observed = observe_local_repository(repo, org, 10)
        self.assertEqual(observed["governanceGuard"], {"declared": False, "status": "not-declared"})

    def test_guard_projection_reports_missing_and_untracked_runners(self) -> None:
        missing = self.make_repo("guard-missing")
        self.install_guard(missing, runner=False)
        untracked = self.make_repo("guard-untracked")
        self.install_guard(untracked, track_runner=False)
        org = {"id": "subactor", "role": "runtime", "ssotCarriers": []}
        repositories = [observe_local_repository(missing, org, 10), observe_local_repository(untracked, org, 10)]
        config = {"organizations": [{"id": "subactor", "governanceExpected": True}]}
        findings = diagnose({"sources": [], "repositories": repositories, "control": {}}, config)
        by_target = {(item["target"], item["code"]) for item in findings}
        self.assertIn(("repo:subactor/guard-missing", "TWIN-WORKTREE-GUARD-RUNNER-MISSING"), by_target)
        self.assertIn(("repo:subactor/guard-untracked", "TWIN-WORKTREE-GUARD-UNTRACKED"), by_target)

    def test_unparseable_document_version_degrades_only_version_field(self) -> None:
        repo = self.make_repo("unparseable-version")
        (repo / "VERSION").write_text("# Version\n\nNo release has been declared.\n" * 20)
        org = {"id": "subactor", "role": "runtime", "ssotCarriers": ["VERSION"]}
        observed = observe_local_repository(repo, org, 10)
        self.assertIsNone(observed["declarations"]["version"])
        self.assertEqual(observed["ssotCarriers"][0]["status"], "valid")
        self.assertIn("git", observed)

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

    def test_anonymous_remote_discovery_is_partial_public_only(self) -> None:
        config = {
            "maxRepositories": 10,
            "organizations": [{"id": "subactor", "required": True, "role": "runtime"}],
        }
        with (
            mock.patch("twin_subactor.sources.shutil.which", return_value=None),
            mock.patch("twin_subactor.sources._remote_repositories_with_http", return_value=[]),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            sources, repositories = discover_remote(config, offline=False)
        self.assertEqual(sources[0]["status"], "partial")
        self.assertEqual(sources[0]["scope"], "public-only")
        self.assertEqual(repositories, [])

    def test_authenticated_http_discovery_can_be_healthy(self) -> None:
        config = {
            "maxRepositories": 10,
            "organizations": [{"id": "subactor", "required": True, "role": "runtime"}],
        }
        item = {"full_name": "subactor/private", "archived": False, "private": True, "default_branch": "main"}
        with (
            mock.patch("twin_subactor.sources.shutil.which", return_value=None),
            mock.patch("twin_subactor.sources._remote_repositories_with_http", return_value=[item]),
            mock.patch.dict(os.environ, {"GITHUB_TOKEN": "test-only-placeholder"}, clear=True),
        ):
            sources, repositories = discover_remote(config, offline=False)
        self.assertEqual(sources[0]["status"], "healthy")
        self.assertEqual(sources[0]["scope"], "authenticated")
        self.assertEqual(repositories[0]["id"], "subactor/private")

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
