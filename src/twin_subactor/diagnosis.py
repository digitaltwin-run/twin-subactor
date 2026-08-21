from __future__ import annotations

from typing import Any

from .sources import digest

SEVERITY = {"critical": ("P0", 100), "error": ("P1", 80), "warning": ("P2", 50), "info": ("P3", 20)}


def _finding(
    code: str,
    severity: str,
    target: str,
    evidence: dict[str, Any],
    *,
    repairability: str,
    route: str,
) -> dict[str, Any]:
    stable = {"code": code, "target": target, "evidence": evidence}
    finding_digest = digest(stable)
    return {
        "code": code,
        "severity": severity,
        "target": target,
        "evidence": evidence,
        "findingDigest": finding_digest,
        "deduplicationKey": digest({"code": code, "target": target}),
        "repairability": repairability,
        "route": route,
    }


def diagnose(snapshot: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for source in snapshot["sources"]:
        if source["status"] == "unavailable":
            findings.append(
                _finding(
                    "TWIN-SOURCE-UNAVAILABLE",
                    "critical" if source["required"] else "warning",
                    f"source:{source['kind']}:{source['id']}",
                    {"status": source["status"], "required": source["required"], "error": source.get("error")},
                    repairability="diagnosis-required",
                    route="doctor-agent",
                )
            )
        elif source["status"] == "partial":
            findings.append(
                _finding(
                    "TWIN-SOURCE-PARTIAL",
                    "error" if source["required"] else "warning",
                    f"source:{source['kind']}:{source['id']}",
                    {"status": source["status"], "errorCount": source.get("errorCount", 0)},
                    repairability="diagnosis-required",
                    route="doctor-agent",
                )
            )

    expected = config.get("expectedGovernanceStandard")
    organizations = {item["id"]: item for item in config.get("organizations", [])}
    for repo in snapshot["repositories"]:
        if not repo.get("local"):
            continue
        if repo.get("sourceObservation", {}).get("status") == "unavailable":
            findings.append(
                _finding(
                    "TWIN-REPOSITORY-OBSERVATION-FAILED",
                    "error",
                    f"repo:{repo['id']}",
                    {"error": repo["sourceObservation"]["error"]},
                    repairability="diagnosis-required",
                    route="doctor-agent",
                )
            )
            continue
        declarations = repo.get("declarations", {})
        git = repo.get("git", {})
        governance_expected = organizations.get(repo.get("organization"), {}).get("governanceExpected", False)
        if governance_expected and not declarations.get("governance"):
            findings.append(
                _finding(
                    "TWIN-GOVERNANCE-MISSING",
                    "error",
                    f"repo:{repo['id']}",
                    {"governance": False, "dirty": git.get("dirty", False)},
                    repairability="grant-required" if not git.get("dirty") else "human-decision-required",
                    route="repair-agent" if not git.get("dirty") else "human",
                )
            )
        standard = declarations.get("standard")
        if isinstance(standard, dict) and standard.get("id") == "wellmanifest/new-project" and expected and standard.get("version") != expected:
            findings.append(
                _finding(
                    "TWIN-STANDARD-VERSION-DIVERGENCE",
                    "warning",
                    f"repo:{repo['id']}",
                    {"observed": standard.get("version"), "expected": expected},
                    repairability="diagnosis-required",
                    route="doctor-agent",
                )
            )
        invalid_carriers = [item["path"] for item in repo.get("ssotCarriers", []) if item.get("status") == "invalid"]
        if invalid_carriers:
            findings.append(
                _finding(
                    "TWIN-SSOT-INVALID",
                    "error",
                    f"repo:{repo['id']}",
                    {"invalidCarriers": invalid_carriers},
                    repairability="diagnosis-required",
                    route="doctor-agent",
                )
            )
        if git.get("dirty"):
            findings.append(
                _finding(
                    "TWIN-WORKTREE-DIRTY",
                    "error",
                    f"repo:{repo['id']}",
                    {"changedPathCount": git.get("changedPathCount", 0)},
                    repairability="human-decision-required",
                    route="human",
                )
            )
        if git.get("upstreamState") == "gone":
            findings.append(
                _finding(
                    "TWIN-UPSTREAM-GONE",
                    "error",
                    f"repo:{repo['id']}",
                    {"branch": git.get("branch")},
                    repairability="human-decision-required",
                    route="human",
                )
            )
        if git.get("behind", 0) > 0:
            findings.append(
                _finding(
                    "TWIN-BRANCH-BEHIND",
                    "warning",
                    f"repo:{repo['id']}",
                    {"behind": git["behind"], "ahead": git.get("ahead", 0)},
                    repairability="diagnosis-required",
                    route="doctor-agent",
                )
            )

    context = snapshot.get("control", {}).get("system-context", {})
    if context and context.get("servicesCount") == 0:
        findings.append(
            _finding(
                "TWIN-CONTROL-SERVICES-EMPTY",
                "error",
                "control:system-context",
                {"servicesCount": 0, "schema": context.get("schema")},
                repairability="diagnosis-required",
                route="doctor-agent",
            )
        )
    state = snapshot.get("control", {}).get("system-state", {})
    registry_counts = [value for key, value in state.items() if key.endswith("registryCount")]
    if state and registry_counts and max(registry_counts) == 0:
        findings.append(
            _finding(
                "TWIN-CONTROL-STATE-REGISTRY-EMPTY",
                "error",
                "control:system-state",
                {"registryCounts": registry_counts},
                repairability="diagnosis-required",
                route="doctor-agent",
            )
        )
    return sorted(findings, key=lambda item: (-SEVERITY[item["severity"]][1], item["code"], item["target"]))


def next_actions(snapshot: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    policy = config["decision"]
    actions: list[dict[str, Any]] = []
    for finding in snapshot["findings"]:
        priority_class, base_score = SEVERITY[finding["severity"]]
        required_source = finding["target"].startswith("source:") and finding["evidence"].get("required")
        score = min(100, base_score + (10 if required_source else 0))
        repairable = finding["repairability"] == "grant-required"
        route = finding["route"]
        pipeline = [
            {"stage": "doctor", "route": "doctor-agent", "skillRef": policy["doctorSkillRef"], "state": "ready" if route != "human" else "blocked-on-human"},
            {
                "stage": "repair",
                "route": "repair-agent",
                "processRef": policy["repairProcessRef"],
                "state": "blocked-on-digest-bound-grant" if repairable else "not-authorized",
            },
            {"stage": "validator", "route": "validator-agent", "processRef": policy["validatorProcessRef"], "state": "blocked-on-exact-repair-result"},
        ]
        actions.append(
            {
                "id": digest({"rule": "twin-subactor.next-action/v1", "finding": finding["findingDigest"]}),
                "snapshotDigest": snapshot["snapshotDigest"],
                "findingDigest": finding["findingDigest"],
                "deduplicationKey": finding["deduplicationKey"],
                "priority": {"class": priority_class, "score": score, "policyRef": policy["policyRef"]},
                "route": route,
                "lifecycleRef": policy["lifecycleRef"],
                "pipeline": pipeline,
                "authority": "external-digest-bound-grant-required-for-mutation",
                "decisionDsl": {
                    "schema": "twin-subactor.next-action-request/v1",
                    "operation": "propose-handoff",
                    "targetRef": finding["target"],
                    "evidenceRefs": [snapshot["snapshotDigest"], finding["findingDigest"]],
                    "llmRole": "rank-equal-deterministic-candidates-only",
                },
            }
        )
    return sorted(actions, key=lambda item: (-item["priority"]["score"], item["id"]))
