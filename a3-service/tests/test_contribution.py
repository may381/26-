"""贡献整理自测（只解释、不创造、不增加）。"""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import contribution as ct  # noqa: E402
import schema_check  # noqa: E402
import v3_messages  # noqa: E402

NOW = datetime(2026, 11, 9, 8, 0, tzinfo=timezone.utc)

ROWS = [
    {"recordId": "c1", "skillName": "剪纸", "minutes": 90, "status": ct.CONFIRMED},
    {"recordId": "c2", "skillName": "剪纸", "minutes": 90, "status": ct.CONFIRMED},
    {"recordId": "c3", "skillName": "书法", "minutes": 60, "status": ct.CONFIRMED},
    {"recordId": "c4", "skillName": "剪纸", "minutes": 90, "status": ct.PENDING},
    {"recordId": "c5", "skillName": "太极", "minutes": 45, "status": ct.REJECTED},
]


class SummarizeTest(unittest.TestCase):
    def test_only_confirmed_counted(self):
        s = ct.summarize(ROWS, now=NOW)
        self.assertEqual(s["totalTimes"], 3)
        self.assertEqual(s["totalMinutes"], 240)
        self.assertEqual(s["pendingCount"], 1)
        self.assertEqual(s["rejectedCount"], 1)

    def test_declares_it_modified_nothing(self):
        """这是给上层看的"我没越权"凭证。"""
        s = ct.summarize(ROWS, now=NOW)
        self.assertFalse(s["a3ModifiedAnything"])
        self.assertEqual(s["countedStatusesOnly"], [ct.CONFIRMED])
        self.assertEqual(s["dataOrigin"], "P2_CONFIRMED_RECORDS")

    def test_grouped_by_skill(self):
        s = ct.summarize(ROWS, now=NOW)
        top = s["skills"][0]
        self.assertEqual(top["skillName"], "剪纸")
        self.assertEqual(top["times"], 2)
        self.assertEqual(top["minutes"], 180)

    def test_out_of_range_minutes_excluded(self):
        rows = ROWS + [{"recordId": "bad", "skillName": "剪纸",
                        "minutes": 99999, "status": ct.CONFIRMED}]
        s = ct.summarize(rows, now=NOW)
        self.assertEqual(s["totalTimes"], 3)
        self.assertIn("bad", s["dirtyRecordIds"])

    def test_negative_minutes_excluded(self):
        rows = [{"recordId": "neg", "skillName": "剪纸",
                 "minutes": -10, "status": ct.CONFIRMED}]
        s = ct.summarize(rows, now=NOW)
        self.assertEqual(s["totalTimes"], 0)
        self.assertIn("neg", s["dirtyRecordIds"])

    def test_bool_minutes_rejected(self):
        rows = [{"recordId": "b", "skillName": "剪纸",
                 "minutes": True, "status": ct.CONFIRMED}]
        s = ct.summarize(rows, now=NOW)
        self.assertEqual(s["totalTimes"], 0)

    def test_only_pending_gives_clear_text(self):
        s = ct.summarize([{"recordId": "p", "status": ct.PENDING, "minutes": 30}], now=NOW)
        self.assertFalse(s["hasData"])
        self.assertIn("确认", s["summaryText"])

    def test_empty_records(self):
        s = ct.summarize([], now=NOW)
        self.assertEqual(s["totalTimes"], 0)
        self.assertFalse(s["hasData"])

    def test_too_many_records_rejected(self):
        with self.assertRaises(ct.ContributionError):
            ct.summarize([{"status": ct.CONFIRMED, "minutes": 1}] * 501)

    def test_hours_formatting(self):
        s = ct.summarize([{"recordId": "a", "skillName": "剪纸",
                           "minutes": 120, "status": ct.CONFIRMED}], now=NOW)
        self.assertIn("2 小时", s["summaryText"])


class ExplainOneTest(unittest.TestCase):
    """单条解释必须和汇总判断一致，不能自相矛盾。"""

    def test_confirmed_counts(self):
        self.assertIn("算数", ct.explain_one(
            {"status": ct.CONFIRMED, "minutes": 90, "skillName": "剪纸"}))

    def test_pending_waits(self):
        text = ct.explain_one({"status": ct.PENDING, "minutes": 90, "skillName": "剪纸"})
        self.assertIn("确认", text)

    def test_rejected_explained(self):
        text = ct.explain_one({"status": ct.REJECTED, "minutes": 45, "skillName": "太极"})
        self.assertIn("没算", text)

    def test_dirty_minutes_flagged_even_if_confirmed(self):
        """汇总把它踢了，单独解释也必须说"不算"，否则老人会困惑。"""
        text = ct.explain_one({"status": ct.CONFIRMED, "minutes": 99999, "skillName": "剪纸"})
        self.assertIn("不对", text)
        self.assertNotIn("算数", text)

    def test_unknown_status(self):
        text = ct.explain_one({"status": "WHATEVER", "minutes": 10})
        self.assertIn("不明确", text)


class CardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        folder = v3_messages.schema_dir()
        cls.root = schema_check.load_schema(os.path.join(folder, "control.schema.json"))

    def test_card_valid(self):
        card = ct.to_card(ct.summarize(ROWS, now=NOW), now=NOW)
        schema_check.validate(card, self.root["definitions"]["Result"], self.root)

    def test_card_is_read_only(self):
        card = ct.to_card(ct.summarize(ROWS, now=NOW), now=NOW)
        self.assertTrue(card["payload"]["readOnly"])
        self.assertFalse(card["payload"]["a3ModifiedAnything"])

    def test_card_pending_checks_state_the_boundary(self):
        joined = " ".join(ct.to_card(ct.summarize(ROWS, now=NOW), now=NOW)["pendingChecks"])
        self.assertIn("不新增", joined)
        self.assertIn("未确认", joined)


if __name__ == "__main__":
    unittest.main(verbosity=2)
