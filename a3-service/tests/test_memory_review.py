"""v3 记忆审核自测（标准库 unittest；有 jsonschema 时额外跑官方 Schema 校验）。

运行：
    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from memory_review import (  # noqa: E402
    ADD, CATEGORY_PREFERENCE, KEEP, MERGE, REJECT, REPLACE,
    classify, normalize_key, review_candidate,
)

SCHEMA_PATH = os.path.join(os.path.dirname(ROOT), "_v3开发包", "agent-v3-r3", "control.schema.json")

try:
    import jsonschema
except ImportError:                                   # 没装就跳过 Schema 校验，不阻断测试
    jsonschema = None


def _load_review_schema():
    if not os.path.exists(SCHEMA_PATH):
        return None
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        return json.load(fh)["definitions"]["MemoryReview"]


REVIEW_SCHEMA = _load_review_schema()

EXISTING = [{
    "memoryId": "memory-001", "version": 2, "key": "mobility.avoidSteps",
    "content": "尽量避开台阶", "value": True, "domains": ["tourism"], "state": "ACTIVE",
}]


def cand(**kwargs):
    base = {"candidateId": "cand-001", "candidateVersion": 1,
            "key": "mobility.avoidSteps", "content": "尽量避开台阶",
            "value": True, "domains": ["tourism"]}
    base.update(kwargs)
    return base


class ClassifyTests(unittest.TestCase):
    """v3 第八节第 1 条：四类信息不能混。"""

    def test_temporary_is_not_saved(self):
        result = classify("今天膝盖有点累")
        self.assertEqual(result["kind"], "TEMPORARY")
        self.assertFalse(result["isLongTerm"])

    def test_long_term_preference(self):
        result = classify("我以后都不走台阶")
        self.assertEqual(result["kind"], CATEGORY_PREFERENCE)
        self.assertTrue(result["isLongTerm"])

    def test_business_fact_is_not_memory(self):
        self.assertEqual(classify("我已经报名了剪纸课")["kind"], "BUSINESS_FACT")

    def test_authorization_is_not_memory(self):
        self.assertEqual(classify("家属能不能看我位置")["kind"], "AUTHORIZATION")

    def test_temporary_plus_long_term_counts_as_long_term(self):
        # "今天累了，以后别走台阶" 里面有长期表述，应该按长期处理
        self.assertTrue(classify("今天累了，以后别走台阶")["isLongTerm"])

    def test_empty_text(self):
        self.assertFalse(classify("   ")["isLongTerm"])


class NormalizeKeyTests(unittest.TestCase):
    """v3：按 userId + 规范化 key + 适用领域 判重，key 必须稳定。"""

    def test_same_meaning_same_key(self):
        self.assertEqual(normalize_key("尽量避开台阶")[0], "mobility.avoidSteps")
        self.assertEqual(normalize_key("完全不能走台阶")[0], "mobility.avoidSteps")

    def test_domain_derived(self):
        self.assertEqual(normalize_key("我走得慢")[1], "tourism")
        self.assertEqual(normalize_key("想学非遗剪纸")[1], "culture")


class ReviewTests(unittest.TestCase):
    def test_add_when_no_conflict(self):
        review = review_candidate(cand(key="mobility.walkSpeed"), [])
        self.assertEqual(review["recommendation"], ADD)
        self.assertTrue(review["needsUserConfirmation"])
        self.assertEqual(review["conflictMemoryRefs"], [])

    def test_keep_when_identical(self):
        review = review_candidate(cand(), EXISTING)
        self.assertEqual(review["recommendation"], KEEP)
        self.assertFalse(review["needsUserConfirmation"])
        self.assertEqual(review["conflictMemoryRefs"], [{"memoryId": "memory-001", "version": 2}])

    def test_replace_when_content_changed(self):
        review = review_candidate(cand(content="完全不能走台阶", candidateVersion=2), EXISTING)
        self.assertEqual(review["recommendation"], REPLACE)
        self.assertTrue(review["needsUserConfirmation"])

    def test_merge_when_domains_widened(self):
        review = review_candidate(cand(domains=["tourism", "culture"]), EXISTING)
        self.assertEqual(review["recommendation"], MERGE)
        self.assertEqual(review["proposedDomains"], ["tourism", "culture"])
        self.assertTrue(review["needsUserConfirmation"])

    def test_reject_sensitive_without_consent(self):
        review = review_candidate(
            cand(key="health.bloodPressure", content="有高血压", domains=["health"],
                 sensitivity="SENSITIVE"), [])
        self.assertEqual(review["recommendation"], REJECT)
        self.assertFalse(review["needsUserConfirmation"])

    def test_sensitive_with_consent_is_allowed(self):
        review = review_candidate(
            cand(key="health.bloodPressure", content="有高血压", domains=["health"],
                 sensitivity="SENSITIVE", sensitiveConsent=True), [])
        self.assertEqual(review["recommendation"], ADD)

    def test_generated_memory_id_must_not_be_invented(self):
        """v3：候选由 P2 生成并保存，A3 不能自己造 candidateId。"""
        with self.assertRaises(ValueError):
            review_candidate({"candidateVersion": 1, "key": "x"}, [])

    def test_conflict_refs_capped(self):
        many = [{"memoryId": f"m-{i}", "version": 1, "key": "mobility.avoidSteps",
                 "content": "尽量避开台阶", "value": True, "domains": ["tourism"],
                 "state": "ACTIVE"} for i in range(15)]
        review = review_candidate(cand(content="完全不能走台阶"), many)
        self.assertLessEqual(len(review["conflictMemoryRefs"]), 10)

    def test_no_extra_fields(self):
        review = review_candidate(cand(), EXISTING)
        self.assertEqual(
            set(review),
            {"candidateId", "candidateVersion", "reviewId", "reviewVersion",
             "recommendation", "conflictMemoryRefs", "proposedDomains",
             "needsUserConfirmation", "explanation"},
        )


@unittest.skipUnless(jsonschema and REVIEW_SCHEMA, "需要 jsonschema 与官方 control.schema.json")
class SchemaConformanceTests(unittest.TestCase):
    """直接拿 P2 的 v3 联调包 Schema 校验，不用等接口上线。"""

    def test_add_matches_official_schema(self):
        jsonschema.validate(review_candidate(cand(key="mobility.walkSpeed"), []), REVIEW_SCHEMA)

    def test_keep_matches_official_schema(self):
        jsonschema.validate(review_candidate(cand(), EXISTING), REVIEW_SCHEMA)

    def test_merge_matches_official_schema(self):
        jsonschema.validate(review_candidate(cand(domains=["tourism", "culture"]), EXISTING),
                            REVIEW_SCHEMA)

    def test_reject_matches_official_schema(self):
        jsonschema.validate(
            review_candidate(cand(key="health.bp", content="有高血压", domains=["health"],
                                  sensitivity="SENSITIVE"), []), REVIEW_SCHEMA)


if __name__ == "__main__":
    unittest.main(verbosity=2)
