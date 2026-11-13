"""非遗文化问答自测（含方言、地方文化，以及"查不到不许编"）。"""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import culture_knowledge as ck  # noqa: E402
import schema_check  # noqa: E402
import v3_messages  # noqa: E402

NOW = datetime(2026, 11, 9, 8, 0, tzinfo=timezone.utc)


class KnowledgeBaseTest(unittest.TestCase):
    """知识库本身的质量约束。"""

    def test_every_entry_has_source(self):
        """没有来源的条目不许进库 —— 这是这个模块的底线。"""
        for entry in ck.KNOWLEDGE:
            with self.subTest(kbId=entry.get("kbId")):
                src = entry.get("source") or {}
                self.assertTrue(src.get("org"), "缺来源机构")
                self.assertTrue(src.get("title"), "缺来源名称")
                self.assertTrue(src.get("note"), "缺核对说明")

    def test_every_entry_has_keywords(self):
        for entry in ck.KNOWLEDGE:
            with self.subTest(kbId=entry["kbId"]):
                self.assertGreaterEqual(len(entry.get("keywords") or []), 2)

    def test_ids_unique(self):
        ids = [e["kbId"] for e in ck.KNOWLEDGE]
        self.assertEqual(len(ids), len(set(ids)))

    def test_covers_three_kinds(self):
        """文档要求「非遗、方言和地方文化」三样，缺一样就是没做到。"""
        kinds = {e["kind"] for e in ck.KNOWLEDGE}
        self.assertEqual(kinds, {"heritage", "dialect", "local"})

    def test_covers_multiple_dialects(self):
        dialects = [e for e in ck.KNOWLEDGE if e["kind"] == "dialect"]
        self.assertGreaterEqual(len(dialects), 3, "方言条目太少")


class SearchTest(unittest.TestCase):
    """匹配行为。虚词不能主导结果，这是第一版踩过的坑。"""

    def ids(self, query, **kwargs):
        return [e["kbId"] for e in ck.search(query, **kwargs)]

    def test_heritage_question_hits_only_that_topic(self):
        self.assertEqual(self.ids("剪纸是什么"), ["kb-papercut"])

    def test_dialect_word_is_understood(self):
        """老人说「唔该」，要能落到粤语条目上，不能被别的标题劫走。"""
        self.assertEqual(self.ids("唔该是什么意思"), ["dl-cantonese"])

    def test_more_dialect_words(self):
        for word, expected in [("巴适", "dl-sichuan"), ("食朝", "dl-hakka"),
                               ("古早", "dl-minnan")]:
            with self.subTest(word=word):
                self.assertIn(expected, self.ids(f"{word}是什么意思"))

    def test_stopwords_do_not_dominate(self):
        """「什么」「怎么」这类词不能把不相干条目带进来。"""
        tokens = ck._tokens("剪纸是什么")
        self.assertEqual(tokens, ["剪纸"])

    def test_unknown_topic_returns_empty(self):
        """库里没有就返回空，不许硬凑 —— 这是防幻觉的核心。"""
        for query in ("景泰蓝怎么烧制", "昆曲的水磨腔怎么唱", "三星堆"):
            with self.subTest(query=query):
                self.assertEqual(ck.search(query), [])

    def test_empty_query_is_rejected(self):
        with self.assertRaises(ck.CultureKnowledgeError) as caught:
            ck.search("   ")
        self.assertEqual(caught.exception.code, "INVALID_ARGUMENT")

    def test_limit_bounds(self):
        with self.assertRaises(ck.CultureKnowledgeError):
            ck.search("文化", limit=0)
        with self.assertRaises(ck.CultureKnowledgeError):
            ck.search("文化", limit=99)

    def test_filter_by_kind(self):
        for item in ck.search("方言", kind="dialect"):
            self.assertEqual(item["kind"], "dialect")

    def test_filter_by_region(self):
        for item in ck.search("广东 文化", region="广东"):
            self.assertIn("广东", item["regions"])

    def test_relative_threshold_drops_weak_matches(self):
        """第一名 10 分、第二名 4 分时，第二名不该出现。"""
        items = ck.search("剪纸是什么")
        self.assertEqual(len(items), 1)

    def test_result_carries_score(self):
        items = ck.search("剪纸")
        self.assertGreater(items[0]["score"], 0)


class AnswerTextTest(unittest.TestCase):
    """说给老人听的话。查不到时最关键。"""

    def test_answers_with_content_and_source(self):
        items = ck.search("剪纸")
        text = ck.build_answer_text(items)
        self.assertIn("剪纸", text)
        self.assertGreater(len(text), 20)

    def test_empty_does_not_fabricate(self):
        """查不到时必须承认查不到，并且给下一步，不能瞎编。"""
        text = ck.build_answer_text([])
        self.assertIn("没有现成资料", text)
        self.assertIn("问", text)
        for fake in ("据记载", "相传", "历史悠久"):
            self.assertNotIn(fake, text)

    def test_dialect_question_detected(self):
        for query in ("唔该是什么意思", "这句话啥意思", "粤语怎么说", "听不懂"):
            with self.subTest(query=query):
                self.assertTrue(ck.is_dialect_question(query))

    def test_non_dialect_not_flagged(self):
        for query in ("想学剪纸", "有什么班"):
            with self.subTest(query=query):
                self.assertFalse(ck.is_dialect_question(query))


class ResultCardTest(unittest.TestCase):
    """卡片要能过官方 Schema。"""

    @classmethod
    def setUpClass(cls):
        folder = v3_messages.schema_dir()
        cls.root = schema_check.load_schema(os.path.join(folder, "control.schema.json"))

    def test_card_passes_official_schema(self):
        card = ck.to_result_card(ck.search("剪纸"), "剪纸是什么", now=NOW)
        schema_check.validate(card, self.root["definitions"]["Result"], self.root)

    def test_card_marks_demo_not_real(self):
        card = ck.to_result_card(ck.search("剪纸"), "剪纸是什么", now=NOW)
        self.assertEqual(card["availability"], "DEMO")

    def test_business_ref_is_null(self):
        card = ck.to_result_card(ck.search("剪纸"), "剪纸是什么", now=NOW)
        self.assertIsNone(card["businessRef"])

    def test_empty_card_still_valid(self):
        card = ck.to_result_card([], "景泰蓝", now=NOW)
        schema_check.validate(card, self.root["definitions"]["Result"], self.root)
        self.assertEqual(card["payload"]["totalCandidates"], 0)
        self.assertIn("没查到", card["title"])

    def test_sources_listed_on_card(self):
        card = ck.to_result_card(ck.search("剪纸"), "剪纸是什么", now=NOW)
        self.assertTrue(card["sources"])
        self.assertTrue(card["sources"][0]["org"])

    def test_pending_checks_mention_verification(self):
        card = ck.to_result_card(ck.search("剪纸"), "剪纸是什么", now=NOW)
        joined = " ".join(card["pendingChecks"])
        self.assertIn("核实", joined)


if __name__ == "__main__":
    unittest.main(verbosity=2)
