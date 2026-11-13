"""v3 候选转换自测：事实 → v3 候选 → 审核建议。"""

from __future__ import annotations

import json
import os
import sys
import unittest
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from candidate_v3 import (  # noqa: E402
    CANDIDATE_TTL_DAYS, DOMAINS, STATE_CANDIDATE,
    build_v3_candidates, review_all, _sensitivity_of,
)
from memory_review import CATEGORY_EXPERIENCE, CATEGORY_PREFERENCE  # noqa: E402

SCHEMA_PATH = os.path.join(os.path.dirname(ROOT), "_v3开发包", "agent-v3-r3", "control.schema.json")
try:
    import jsonschema
except ImportError:
    jsonschema = None

FACTS = {
    "routeId": "r-001", "routeName": "省力线",
    "startedAt": "2026-10-29T01:00:00Z", "endedAt": "2026-10-29T01:40:00Z",
    "visitedSpots": ["迎客松", "清风湖"],
    "feedback": "走40分钟就累，最好少走台阶",
    "restStops": 2, "source": "GPS",
}
CREATED = datetime(2026, 10, 29, tzinfo=timezone.utc)


class BuildTests(unittest.TestCase):
    def setUp(self) -> None:
        self.built = build_v3_candidates("u100", "t-demo-001", FACTS, created_at=CREATED)
        self.cands = self.built["candidates"]

    def test_generates_three_candidates(self):
        keys = sorted(c["key"] for c in self.cands)
        self.assertEqual(keys, ["activity.preferredDurationMin",
                                "experience.tripSummary",
                                "mobility.avoidSteps"])

    def test_categories_are_v3_allowed(self):
        for c in self.cands:
            self.assertIn(c["category"], (CATEGORY_PREFERENCE, CATEGORY_EXPERIENCE))

    def test_domains_are_registered_only(self):
        for c in self.cands:
            for d in c["domains"]:
                self.assertIn(d, DOMAINS, f"自造领域 {d}")

    def test_state_is_candidate(self):
        for c in self.cands:
            self.assertEqual(c["state"], STATE_CANDIDATE)

    def test_expires_in_seven_days(self):
        for c in self.cands:
            self.assertEqual(c["expiresAt"], "2026-11-05T00:00:00Z")

    def test_ttl_matches_constant(self):
        self.assertEqual(self.built["candidateTtlDays"], CANDIDATE_TTL_DAYS)

    def test_candidate_id_is_stable_across_runs(self):
        again = build_v3_candidates("u100", "t-demo-001", FACTS, created_at=CREATED)
        self.assertEqual([c["candidateId"] for c in self.cands],
                         [c["candidateId"] for c in again["candidates"]])

    def test_candidate_id_differs_across_trips(self):
        other = build_v3_candidates("u100", "t-demo-002", FACTS, created_at=CREATED)
        self.assertNotEqual(self.cands[0]["candidateId"], other["candidates"][0]["candidateId"])

    def test_evidence_is_kept(self):
        for c in self.cands:
            self.assertTrue(c["evidence"], "候选必须保留溯源")

    def test_legacy_dedupe_key_kept_for_traceability(self):
        self.assertTrue(all(c["legacyDedupeKey"] for c in self.cands))

    def test_health_key_is_sensitive(self):
        self.assertEqual(_sensitivity_of("health.bloodPressure"), "SENSITIVE")
        self.assertEqual(_sensitivity_of("mobility.avoidSteps"), "GENERAL")


class ReviewPipelineTests(unittest.TestCase):
    def test_reviews_cover_every_candidate(self):
        built = build_v3_candidates("u100", "t-demo-001", FACTS, created_at=CREATED)
        reviews = review_all(built["candidates"])
        self.assertEqual(len(reviews), len(built["candidates"]))
        for review in reviews:
            self.assertTrue(review["explanation"])
            self.assertNotIn("confirmationId", review, "v3：A3 不得伪造 confirmationId")

    def test_keep_when_same_key_exists(self):
        built = build_v3_candidates("u100", "t-demo-001", FACTS, created_at=CREATED)
        existing = [{"memoryId": "memory-001", "version": 2, "key": "mobility.avoidSteps",
                     "content": "尽量避开台阶路线", "value": True,
                     "domains": ["tourism"], "state": "ACTIVE"}]
        reviews = {r["candidateId"]: r for r in review_all(built["candidates"], existing)}
        steps = [c for c in built["candidates"] if c["key"] == "mobility.avoidSteps"][0]
        self.assertEqual(reviews[steps["candidateId"]]["recommendation"], "KEEP")


@unittest.skipUnless(jsonschema and os.path.exists(SCHEMA_PATH), "需要 jsonschema 与官方 Schema")
class SchemaTests(unittest.TestCase):
    def test_all_reviews_pass_official_schema(self):
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            schema = json.load(fh)["definitions"]["MemoryReview"]
        built = build_v3_candidates("u100", "t-demo-001", FACTS, created_at=CREATED)
        for review in review_all(built["candidates"]):
            jsonschema.validate(review, schema)


if __name__ == "__main__":
    unittest.main(verbosity=2)
