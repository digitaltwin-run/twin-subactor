from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .sources import digest

PURPOSE_SCHEMA = "twin-subactor.organism-purpose/v1"
TOKEN_SCHEMA = "twin-subactor.process-token/v1"
ALLOWED_ROUTES = {"doctor-agent", "repair-agent", "validator-agent", "human"}
MAX_PURPOSE_TEXT = 12_000


def _strings(value: Any, field: str, *, maximum: int = 64) -> list[str]:
    if not isinstance(value, list) or not value or len(value) > maximum:
        raise ValueError(f"purpose_{field}_invalid")
    if any(not isinstance(item, str) or not item.strip() or len(item) > 512 for item in value):
        raise ValueError(f"purpose_{field}_invalid")
    return value


def validate_purpose(purpose: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(purpose, dict):
        raise ValueError("purpose_document_invalid")
    allowed = {"schema", "status", "sourceNl", "mission", "invariants", "knowledgeRefs", "scope", "policy", "interaction"}
    if set(purpose) != allowed:
        raise ValueError("purpose_fields_invalid")
    if purpose.get("schema") != PURPOSE_SCHEMA or purpose.get("status") != "accepted":
        raise ValueError("purpose_not_accepted")
    for field in ("sourceNl", "mission"):
        value = purpose.get(field)
        if not isinstance(value, str) or not value.strip() or len(value) > MAX_PURPOSE_TEXT:
            raise ValueError(f"purpose_{field}_invalid")
    _strings(purpose.get("invariants"), "invariants", maximum=32)
    knowledge_refs = _strings(purpose.get("knowledgeRefs"), "knowledge_refs", maximum=32)
    if any(not reference.startswith("knowledge://subactor/") or "/v" not in reference for reference in knowledge_refs):
        raise ValueError("purpose_knowledge_ref_invalid")

    scope = purpose.get("scope")
    if not isinstance(scope, dict) or set(scope) != {"targetPrefixes"}:
        raise ValueError("purpose_scope_invalid")
    prefixes = _strings(scope.get("targetPrefixes"), "target_prefixes", maximum=64)
    if any(not prefix.startswith(("repo:", "source:", "control:")) for prefix in prefixes):
        raise ValueError("purpose_target_prefix_invalid")

    policy = purpose.get("policy")
    if not isinstance(policy, dict) or set(policy) != {"allowedRoutes", "mutationAuthority", "idleAction"}:
        raise ValueError("purpose_policy_invalid")
    routes = _strings(policy.get("allowedRoutes"), "allowed_routes", maximum=4)
    if not set(routes).issubset(ALLOWED_ROUTES):
        raise ValueError("purpose_route_invalid")
    if policy.get("mutationAuthority") != "external-digest-bound-grant-only":
        raise ValueError("purpose_mutation_authority_invalid")
    if policy.get("idleAction") != "wait-for-context-change":
        raise ValueError("purpose_idle_action_invalid")

    interaction = purpose.get("interaction")
    if not isinstance(interaction, dict) or set(interaction) != {"channel", "founderRequiredFor"}:
        raise ValueError("purpose_interaction_invalid")
    if interaction.get("channel") != "founder-shell":
        raise ValueError("purpose_interaction_channel_invalid")
    _strings(interaction.get("founderRequiredFor"), "founder_required_for", maximum=16)
    return purpose


def load_purpose(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("purpose_unreadable") from error
    return validate_purpose(value)


def _eligible_actions(snapshot: dict[str, Any], purpose: dict[str, Any]) -> list[dict[str, Any]]:
    prefixes = tuple(purpose["scope"]["targetPrefixes"])
    routes = set(purpose["policy"]["allowedRoutes"])
    actions = []
    for action in snapshot.get("nextActions", []):
        target = action.get("decisionDsl", {}).get("targetRef", "")
        if action.get("route") in routes and target.startswith(prefixes):
            actions.append(action)
    def rank(item: dict[str, Any]) -> tuple[int, int, str]:
        target = item["decisionDsl"]["targetRef"]
        purpose_rank = next(index for index, prefix in enumerate(prefixes) if target.startswith(prefix))
        return (-item["priority"]["score"], purpose_rank, item["id"])

    return sorted(actions, key=rank)


def _projected_action(action: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": action["id"],
        "findingDigest": action["findingDigest"],
        "deduplicationKey": action["deduplicationKey"],
        "targetRef": action["decisionDsl"]["targetRef"],
        "route": action["route"],
        "priority": action["priority"],
        "pipeline": action["pipeline"],
    }


def next_process_token(
    snapshot: dict[str, Any],
    purpose: dict[str, Any],
    *,
    sequence: int = 0,
    previous_token_digest: str | None = None,
) -> dict[str, Any]:
    validate_purpose(purpose)
    snapshot_digest = snapshot.get("snapshotDigest")
    if not isinstance(snapshot_digest, str) or not snapshot_digest.startswith("sha256:"):
        raise ValueError("snapshot_digest_invalid")
    if not isinstance(sequence, int) or sequence < 0:
        raise ValueError("sequence_invalid")
    if previous_token_digest is not None and not previous_token_digest.startswith("sha256:"):
        raise ValueError("previous_token_digest_invalid")

    purpose_digest = digest(purpose)
    eligible = _eligible_actions(snapshot, purpose)
    selected = _projected_action(eligible[0]) if eligible else None
    if selected is None:
        phase = "wait"
        operation = "wait-for-context-change"
        route = "twin-subactor"
        projection_uri = "twin-subactor://evolution/wait"
        postcondition = "resume-only-after-snapshot-or-receipt-digest-change"
    elif selected["route"] == "human":
        phase = "interaction"
        operation = "request-founder-decision"
        route = "human"
        projection_uri = f"twin-subactor://evolution/ask-founder/{selected['id'].removeprefix('sha256:')}"
        postcondition = "founder-response-must-become-a-separate-accepted-intent-or-authority-receipt"
    else:
        phase = "propose"
        operation = "propose-governed-handoff"
        route = selected["route"]
        projection_uri = f"twin-subactor://evolution/handoff/{selected['id'].removeprefix('sha256:')}"
        postcondition = "control-receipt-and-independent-eql-required-before-context-advance"

    decision = {
        "phase": phase,
        "operation": operation,
        "route": route,
        "projectionUri": projection_uri,
        "selectedAction": selected,
        "candidateCount": len(eligible),
        "rankingRule": "system-priority-then-accepted-purpose-prefix-order-then-stable-id",
    }
    decision_digest = digest(
        {
            "rule": "twin-subactor.next-process-decision/v1",
            "purposeDigest": purpose_digest,
            "snapshotDigest": snapshot_digest,
            "decision": decision,
        }
    )
    token: dict[str, Any] = {
        "schema": TOKEN_SCHEMA,
        "sequence": sequence,
        "purposeDigest": purpose_digest,
        "snapshotDigest": snapshot_digest,
        "previousTokenDigest": previous_token_digest,
        "decisionDigest": decision_digest,
        "decision": decision,
        "adapterChain": [
            {"adapter": "nl2dsl", "state": "completed-upstream", "evidenceRef": purpose_digest},
            {"adapter": "env2dsl", "state": "completed", "evidenceRef": snapshot_digest},
            {"adapter": "intent2dsl", "state": "accepted-purpose-input"},
            {"adapter": "dsl2intent", "state": "read-only-explanation-available"},
            {"adapter": "nl2uri", "state": "forbidden-direct", "replacement": "capability-to-uri-catalog-binder"},
            {"adapter": "uri2nl", "state": "available-after-exact-binding"},
        ],
        "runtimeBinding": {
            "status": "not-bound" if selected is None or route == "human" else "requires-control-catalog-binding",
            "executableUri": None,
            "rule": "an-llm-or-twin-must-not-invent-an-executable-uri",
        },
        "authority": {
            "twinMayAct": False,
            "mutation": "external-digest-bound-grant-required",
            "completion": "independent-eql-and-receipt-required",
        },
        "eql": {
            "preconditions": ["purpose-status-is-accepted", "snapshot-digest-is-exact"],
            "postcondition": postcondition,
        },
        "rollback": {
            "projection": "not-required-read-only",
            "downstreamMutation": "must-declare-exact-compensator-before-apply",
        },
        "continuation": {
            "mode": "event-driven",
            "resumeOn": ["snapshot-digest-change", "execution-receipt", "founder-response"],
            "busyLoopAllowed": False,
        },
    }
    token["tokenDigest"] = digest(token)
    return token
