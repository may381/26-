"""v3 检索策略自测（memory.search 的筛选与配额）。"""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from memory_search import (  # noqa: E402
    READ_AVAILABLE, READ_EMPTY, MemorySearchError,
    search, to_error_response, to_tool_response, validate_args,
)

AUTH = ["tourism", "culture"]

MEMORIES = [
    {"memoryId": "m-1", "version": 2, "category": "LONG_TERM_PREFERENCE",
     "key": "activity.preferredDurationMin", "content": "平时更喜欢一小时以内的文化活动",
     "value": 60, "domains": ["tourism", "culture"], "sensitivity": "GENERAL",
     "state": "ACTIVE", "updatedAt": "2026-10-28T02:00:00Z"},
    {"memoryId": "m-2", "version": 1, "category": "LONG_TERM_PREFERENCE",
     "key": "culture.interests", "content": "喜欢剪纸和刺绣",
     "value": None, "domains": ["culture"], "sensitivity": "GENERAL",
     "state": "ACTIVE", "updatedAt": "2026-10-27T02:00:00Z"},
    {"memoryId": "m-3", "version": 1, "category": "LONG_TERM_PREFERENCE",
     "key": "health.bloodPressure", "content": "有高血压，需要少盐饮食",
     "value": None, "domains": ["health"], "sensitivity": "SENSITIVE",
     "state": "ACTIVE", "updatedAt": "2026-10-26T02:00:00Z"},
    {"memoryId": "m-4", "version": 1, "category": "LONG_TERM_PREFERENCE",
     "key": "culture.oldPreference", "content": "以前喜欢剪纸",
     "value": None, "domains": ["culture"], "sensitivity": "GENERAL",
     "state": "SUPERSEDED", "updatedAt": "2026-10-20T02:00:00Z"},
    {"memoryId": "m-5", "version": 1, "category": "LONG_TERM_PREFERENCE",
     "key": "culture.pending", "content": "想学剪纸，待确认",
     "value": None, "domains": ["culture"], "sensitivity": "GENERAL",
     "state": "CANDIDATE", "updatedAt": "2026-10-29T02:00:00Z"},
]

BASE_ARGS = {"purpose": "安排文化活动", "query": "剪纸", "domains": ["culture"], "limit": 5}


class ValidateTests(unittest.TestCase):
    def test_missing_purpose(self):
        with self.assertRaises(MemorySearchError) as ctx:
            validate_args({"query": "剪纸"})
        self.assertEqual(ctx.exception.status, 400)

    def test_missing_query(self):
        with self.assertRaises(MemorySearchError):
            validate_args({"purpose": "安排活动"})

    def test_purpose_too_long(self):
        with self.assertRaises(MemorySearchError):
            validate_args({"purpose": "长" * 501, "query": "剪纸"})

    def test_query_too_long(self):
        with self.assertRaises(MemorySearchError):
            validate_args({"purpose": "安排活动", "query": "剪" * 1001})

    def test_domains_max_three(self):
        with self.assertRaises(MemorySearchError):
            validate_args({"purpose": "p", "query": "q",
                           "domains": ["tourism", "culture", "care", "help"]})

    def test_unregistered_domain(self):
        with self.assertRaises(MemorySearchError) as ctx:
            validate_args({"purpose": "p", "query": "q", "domains": ["mobility"]})
        self.assertIn("未登记的领域", ctx.exception.message)

    def test_limit_bounds(self):
        for bad in (0, 11, "5", True):
            with self.assertRaises(MemorySearchError):
                validate_args({"purpose": "p", "query": "q", "limit": bad})

    def test_max_content_chars_bounds(self):
        for bad in (199, 4001):
            with self.assertRaises(MemorySearchError):
                validate_args({"purpose": "p", "query": "q", "maxContentChars": bad})

    def test_unknown_field(self):
        with self.assertRaises(MemorySearchError):
            validate_args({"purpose": "p", "query": "q", "userId": "u100"})

    def test_defaults_applied(self):
        checked = validate_args({"purpose": " 安排活动 ", "query": " 剪纸 "})
        self.assertEqual(checked["limit"], 5)
        self.assertEqual(checked["maxContentChars"], 2000)
        self.assertEqual(checked["purpose"], "安排活动")


class SearchTests(unittest.TestCase):
    def test_returns_matching_active_only(self):
        result = search(BASE_ARGS, MEMORIES, authorized_domains=AUTH)
        ids = [i["memoryId"] for i in result["items"]]
        self.assertEqual(result["readStatus"], READ_AVAILABLE)
        self.assertIn("m-2", ids)
        self.assertNotIn("m-4", ids, "SUPERSEDED 不能返回")
        self.assertNotIn("m-5", ids, "CANDIDATE 不能当长期事实返回")

    def test_empty_when_no_keyword_match(self):
        result = search({"purpose": "查探戈课程", "query": "探戈", "domains": ["culture"]},
                        MEMORIES, authorized_domains=AUTH)
        self.assertEqual(result["readStatus"], READ_EMPTY)
        self.assertEqual(result["items"], [])

    def test_forbidden_domain_does_not_leak(self):
        with self.assertRaises(MemorySearchError) as ctx:
            search({"purpose": "查健康", "query": "血压", "domains": ["health"]},
                   MEMORIES, authorized_domains=["tourism"])
        self.assertEqual(ctx.exception.status, 403)
        self.assertNotIn("m-3", ctx.exception.message)

    def test_unavailable_is_503_not_empty(self):
        with self.assertRaises(MemorySearchError) as ctx:
            search(BASE_ARGS, MEMORIES, authorized_domains=AUTH, store_available=False)
        self.assertEqual(ctx.exception.status, 503)
        self.assertEqual(ctx.exception.code, "CAPABILITY_UNAVAILABLE")

    def test_sensitive_needs_authorization(self):
        result = search({"purpose": "查血压", "query": "血压", "domains": ["health"]},
                        MEMORIES, authorized_domains=["health"])
        self.assertEqual(result["readStatus"], READ_AVAILABLE)
        self.assertEqual(result["items"][0]["memoryId"], "m-3")

        # 有授权列表但不含 health → 403（越权先于敏感判断）
        with self.assertRaises(MemorySearchError):
            search({"purpose": "查血压", "query": "血压", "domains": ["health"]},
                   MEMORIES, authorized_domains=["tourism"])

    def test_sensitive_hidden_when_no_authorization_list(self):
        result = search({"purpose": "查血压", "query": "血压"}, MEMORIES,
                        authorized_domains=None)
        self.assertNotIn("m-3", [i["memoryId"] for i in result["items"]])

    def test_limit_respected(self):
        result = search(dict(BASE_ARGS, limit=1), MEMORIES, authorized_domains=AUTH)
        self.assertEqual(len(result["items"]), 1)
        self.assertTrue(result["truncated"])

    def test_budget_skips_whole_items(self):
        long_memories = [
            {"memoryId": f"m-long-{i}", "version": 1, "category": "LONG_TERM_PREFERENCE",
             "key": f"culture.n{i}", "content": "文化活动" + "说" * 80,
             "domains": ["culture"], "sensitivity": "GENERAL", "state": "ACTIVE",
             "updatedAt": f"2026-10-2{i}T02:00:00Z"}
            for i in range(1, 4)
        ]
        result = search({"purpose": "安排活动", "query": "文化活动", "domains": ["culture"],
                         "limit": 10, "maxContentChars": 200},
                        long_memories, authorized_domains=["culture"])
        self.assertTrue(result["truncated"])
        self.assertLessEqual(result["returnedContentChars"], 200)
        for item in result["items"]:
            self.assertTrue(item["content"].endswith("说"), "内容不能被截断")

    def test_oversized_single_item_is_skipped(self):
        big = [{"memoryId": "m-big", "version": 1, "category": "LONG_TERM_PREFERENCE",
                "key": "culture.big", "content": "剪纸" + "长" * 1200,
                "domains": ["culture"], "sensitivity": "GENERAL", "state": "ACTIVE",
                "updatedAt": "2026-10-28T02:00:00Z"}]
        result = search({"purpose": "安排活动", "query": "剪纸", "domains": ["culture"]},
                        big, authorized_domains=["culture"])
        self.assertEqual(result["readStatus"], READ_EMPTY)
        self.assertTrue(result["truncated"])

    def test_expired_memory_filtered(self):
        past = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        expired = [{"memoryId": "m-exp", "version": 1, "category": "LONG_TERM_PREFERENCE",
                    "key": "culture.exp", "content": "剪纸旧偏好",
                    "domains": ["culture"], "sensitivity": "GENERAL", "state": "ACTIVE",
                    "updatedAt": "2026-10-20T02:00:00Z", "expiresAt": past}]
        result = search({"purpose": "安排活动", "query": "剪纸", "domains": ["culture"]},
                        expired, authorized_domains=["culture"])
        self.assertEqual(result["readStatus"], READ_EMPTY)

    def test_same_key_only_highest_version(self):
        dup = [
            {"memoryId": "m-v1", "version": 1, "category": "LONG_TERM_PREFERENCE",
             "key": "culture.interest", "content": "喜欢剪纸",
             "domains": ["culture"], "sensitivity": "GENERAL", "state": "ACTIVE",
             "updatedAt": "2026-10-20T02:00:00Z"},
            {"memoryId": "m-v3", "version": 3, "category": "LONG_TERM_PREFERENCE",
             "key": "culture.interest", "content": "喜欢剪纸和刺绣",
             "domains": ["culture"], "sensitivity": "GENERAL", "state": "ACTIVE",
             "updatedAt": "2026-10-28T02:00:00Z"},
        ]
        result = search({"purpose": "安排活动", "query": "剪纸", "domains": ["culture"]},
                        dup, authorized_domains=["culture"])
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["memoryId"], "m-v3")

    def test_item_shape_is_contract_only(self):
        result = search(BASE_ARGS, MEMORIES, authorized_domains=AUTH)
        expected = {"memoryId", "version", "category", "key", "content", "value",
                    "domains", "sensitivity", "state", "sourceRefs",
                    "confirmedAt", "updatedAt", "expiresAt"}
        for item in result["items"]:
            self.assertEqual(set(item), expected)
            self.assertIsInstance(item["sourceRefs"], list)

    def test_revisions_passed_through(self):
        result = search(BASE_ARGS, MEMORIES, authorized_domains=AUTH,
                        memory_revision=12, authorization_revision=4)
        self.assertEqual(result["memoryRevision"], 12)
        self.assertEqual(result["authorizationRevision"], 4)


class WrapperTests(unittest.TestCase):
    def test_tool_response_shape(self):
        result = search(BASE_ARGS, MEMORIES, authorized_domains=AUTH)
        wrapped = to_tool_response(result)
        self.assertEqual(wrapped["code"], "OK")
        self.assertEqual(wrapped["data"]["tool"], "memory.search")
        self.assertIn("result", wrapped["data"])

    def test_error_response_has_null_data(self):
        wrapped = to_error_response(MemorySearchError(403, "FORBIDDEN", "越权"))
        self.assertEqual(wrapped, {"code": "FORBIDDEN", "message": "越权", "data": None})


if __name__ == "__main__":
    unittest.main(verbosity=2)
