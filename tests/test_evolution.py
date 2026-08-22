from __future__ import annotations

import json
import unittest
from pathlib import Path

from twin_subactor.evolution import load_purpose, next_process_token, validate_purpose
from twin_subactor.sources import digest


ROOT = Path(__file__).resolve().parents[1]


def action(route: str = "repair-agent", target: str = "repo:subactor/core", score: int = 80) -> dict:
    finding_digest = digest({"finding": target})
    return {
        "id": digest({"action": target}),
        "snapshotDigest": digest({"snapshot": 1}),
        "findingDigest": finding_digest,
        "deduplicationKey": digest({"dedupe": target}),
        "priority": {"class": "P1", "score": score, "policyRef": "priority://test/v1"},
        "route": route,
        "pipeline": [{"stage": "doctor", "route": "doctor-agent", "state": "ready"}],
        "decisionDsl": {"targetRef": target},
    }


class EvolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.purpose = load_purpose(ROOT / "docs/examples/subactor-purpose.v1.json")

    def snapshot(self, actions: list[dict]) -> dict:
        return {"snapshotDigest": digest({"snapshot": 1}), "nextActions": actions}

    def test_same_purpose_and_snapshot_produce_same_decision(self) -> None:
        snapshot = self.snapshot([action()])
        first = next_process_token(snapshot, self.purpose)
        second = next_process_token(snapshot, self.purpose, sequence=7, previous_token_digest=first["tokenDigest"])

        self.assertEqual(first["decisionDigest"], second["decisionDigest"])
        self.assertNotEqual(first["tokenDigest"], second["tokenDigest"])
        self.assertEqual(second["previousTokenDigest"], first["tokenDigest"])
        self.assertFalse(first["authority"]["twinMayAct"])
        self.assertIsNone(first["runtimeBinding"]["executableUri"])

    def test_human_route_becomes_founder_interaction(self) -> None:
        token = next_process_token(self.snapshot([action(route="human")]), self.purpose)

        self.assertEqual(token["decision"]["phase"], "interaction")
        self.assertEqual(token["decision"]["operation"], "request-founder-decision")
        self.assertTrue(token["decision"]["projectionUri"].startswith("twin-subactor://evolution/ask-founder/"))
        self.assertEqual(token["runtimeBinding"]["status"], "not-bound")

    def test_no_eligible_action_waits_for_context_change(self) -> None:
        token = next_process_token(self.snapshot([action(target="repo:oqlos/example")]), self.purpose)

        self.assertEqual(token["decision"]["operation"], "wait-for-context-change")
        self.assertEqual(token["decision"]["candidateCount"], 0)
        self.assertFalse(token["continuation"]["busyLoopAllowed"])

    def test_direct_nl_to_uri_is_explicitly_forbidden(self) -> None:
        token = next_process_token(self.snapshot([action()]), self.purpose)
        adapters = {item["adapter"]: item for item in token["adapterChain"]}

        self.assertEqual(adapters["nl2uri"]["state"], "forbidden-direct")
        self.assertEqual(token["runtimeBinding"]["status"], "requires-control-catalog-binding")

    def test_accepted_purpose_order_breaks_only_equal_priority_ties(self) -> None:
        token = next_process_token(
            self.snapshot([
                action(target="repo:semcod/pyqual", score=80),
                action(target="repo:subactor/core", score=80),
                action(target="repo:wellmanifest/skills", score=100),
            ]),
            self.purpose,
        )

        self.assertEqual(token["decision"]["selectedAction"]["targetRef"], "repo:wellmanifest/skills")
        without_higher_system_priority = next_process_token(
            self.snapshot([
                action(target="repo:semcod/pyqual", score=80),
                action(target="repo:subactor/core", score=80),
            ]),
            self.purpose,
        )
        self.assertEqual(without_higher_system_priority["decision"]["selectedAction"]["targetRef"], "repo:subactor/core")

    def test_unaccepted_or_extra_purpose_fields_fail_closed(self) -> None:
        proposed = json.loads(json.dumps(self.purpose))
        proposed["status"] = "proposed"
        with self.assertRaisesRegex(ValueError, "purpose_not_accepted"):
            validate_purpose(proposed)

        expanded = json.loads(json.dumps(self.purpose))
        expanded["execute"] = True
        with self.assertRaisesRegex(ValueError, "purpose_fields_invalid"):
            validate_purpose(expanded)


if __name__ == "__main__":
    unittest.main()
