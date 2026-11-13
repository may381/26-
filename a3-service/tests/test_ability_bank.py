"""能力银行自测（技能识别、传授意愿、流程边界、供需匹配）。"""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import ability_bank as ab  # noqa: E402
import schema_check  # noqa: E402
import v3_messages  # noqa: E402

NOW = datetime(2026, 11, 9, 8, 0, tzinfo=timezone.utc)


class ParseSkillTest(unittest.TestCase):
    def test_public_willingness(self):
        p = ab.parse_skill("我会剪纸，愿意教大家，一周能安排两次")
        self.assertEqual(p["skillName"], "剪纸")
        self.assertEqual(p["willingness"], ab.WILL_PUBLIC)
        self.assertEqual(p["weeklySlots"], 2)

    def test_acquaintance_only(self):
        p = ab.parse_skill("我做裁缝，可以教教邻居")
        self.assertEqual(p["willingness"], ab.WILL_ACQUAINTANCE)

    def test_refuses_to_teach(self):
        p = ab.parse_skill("我会做饭，不教别人")
        self.assertEqual(p["willingness"], ab.WILL_NONE)

    def test_unstated_defaults_to_conservative(self):
        """只说会什么、没说愿不愿意教 —— 不能默认"愿意公开教"。"""
        p = ab.parse_skill("我以前是做裁缝的")
        self.assertEqual(p["willingness"], ab.WILL_ACQUAINTANCE)

    def test_unknown_skill_returns_none(self):
        """认不出技能就不生成登记，不能让老人收到"您已登记…"。"""
        for text in ("我喜欢听戏", "今天天气不错", "想找人聊天"):
            with self.subTest(text=text):
                self.assertIsNone(ab.parse_skill(text))

    def test_empty_text(self):
        self.assertIsNone(ab.parse_skill(""))
        self.assertIsNone(ab.parse_skill(None))

    def test_slots_variants(self):
        for text, expect in [("我会太极，一周三次", 3),
                             ("我会书法，一周可以教两次", 2),
                             ("我会剪纸，一周一次", 1)]:
            with self.subTest(text=text):
                self.assertEqual(ab.parse_skill(text)["weeklySlots"], expect)

    def test_slots_clamped(self):
        p = ab.parse_skill("我会剪纸，一周七次")
        self.assertLessEqual(p["weeklySlots"], ab.MAX_SLOTS_PER_WEEK)


class SkillRecordTest(unittest.TestCase):
    def setUp(self):
        self.parsed = ab.parse_skill("我会剪纸，愿意教大家")

    def test_starts_as_submitted_not_published(self):
        """A3 没有权力让技能直接上线。"""
        rec = ab.build_skill_record("u100", self.parsed, now=NOW)
        self.assertEqual(rec["state"], ab.STAGE_SUBMITTED)

    def test_requires_user_id(self):
        with self.assertRaises(ab.AbilityBankError):
            ab.build_skill_record("", self.parsed)

    def test_rejects_empty_parse(self):
        with self.assertRaises(ab.AbilityBankError):
            ab.build_skill_record("u100", {})

    def test_stable_id_for_same_user_and_skill(self):
        a = ab.build_skill_record("u100", self.parsed, now=NOW)
        b = ab.build_skill_record("u100", self.parsed, now=NOW)
        self.assertEqual(a["skillId"], b["skillId"])

    def test_different_users_get_different_ids(self):
        a = ab.build_skill_record("u100", self.parsed, now=NOW)
        b = ab.build_skill_record("u200", self.parsed, now=NOW)
        self.assertNotEqual(a["skillId"], b["skillId"])


class NextActionTest(unittest.TestCase):
    """流程解释：每个阶段谁该动。"""

    def record(self, state):
        return {"skillId": "s1", "state": state}

    def test_submitted_waits_for_review_and_a3_cannot_advance(self):
        a = ab.next_action(self.record(ab.STAGE_SUBMITTED))
        self.assertEqual(a["owner"], "P2")
        self.assertFalse(a["a3CanAdvance"])

    def test_no_state_lets_a3_approve(self):
        """任何状态下，A3 都不能把"待审核"变成"已发布"。"""
        for state in ab.STAGES:
            with self.subTest(state=state):
                a = ab.next_action(self.record(state))
                self.assertIn("owner", a)
                if state in (ab.STAGE_SUBMITTED, ab.STAGE_REVIEWING):
                    self.assertFalse(a["a3CanAdvance"])

    def test_unknown_state_rejected(self):
        with self.assertRaises(ab.AbilityBankError):
            ab.next_action({"state": "APPROVED"})


class MatchTest(unittest.TestCase):
    def supply(self, sid, state=ab.STAGE_PUBLISHED, will=ab.WILL_PUBLIC,
               slots=2, region="广东"):
        return {"skillId": sid, "userId": "u-" + sid, "skillName": "剪纸",
                "willingness": will, "weeklySlots": slots,
                "state": state, "region": region}

    def demand(self):
        return [{"demandId": "d1", "skillName": "剪纸", "region": "广东"}]

    def test_only_published_participates(self):
        supplies = [self.supply("a", state=ab.STAGE_REVIEWING)]
        self.assertEqual(ab.match_supply_demand(supplies, self.demand()), [])

    def test_refusing_teacher_not_matched(self):
        supplies = [self.supply("a", will=ab.WILL_NONE)]
        self.assertEqual(ab.match_supply_demand(supplies, self.demand()), [])

    def test_match_is_not_confirmed(self):
        """匹配只是推荐，绝不承诺有人来。"""
        ms = ab.match_supply_demand([self.supply("a")], self.demand())
        self.assertTrue(ms)
        self.assertFalse(ms[0]["confirmed"])

    def test_public_willingness_scores_higher(self):
        supplies = [self.supply("pub", will=ab.WILL_PUBLIC),
                    self.supply("acq", will=ab.WILL_ACQUAINTANCE)]
        ms = ab.match_supply_demand(supplies, self.demand(), limit=2)
        self.assertEqual(ms[0]["supplySkillId"], "pub")

    def test_limit_bounds(self):
        with self.assertRaises(ab.AbilityBankError):
            ab.match_supply_demand([], [], limit=0)


class CardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        folder = v3_messages.schema_dir()
        cls.root = schema_check.load_schema(os.path.join(folder, "control.schema.json"))

    def test_skill_card_valid(self):
        rec = ab.build_skill_record("u100", ab.parse_skill("我会剪纸，愿意教"), now=NOW)
        card = ab.to_skill_card(rec, now=NOW)
        schema_check.validate(card, self.root["definitions"]["Result"], self.root)
        self.assertEqual(card["availability"], "DEMO")
        self.assertIsNone(card["businessRef"])

    def test_skill_card_states_no_auto_approval(self):
        rec = ab.build_skill_record("u100", ab.parse_skill("我会剪纸，愿意教"), now=NOW)
        joined = " ".join(ab.to_skill_card(rec, now=NOW)["pendingChecks"])
        self.assertIn("不代替审核", joined)
        self.assertIn("时长", joined)

    def test_match_card_valid(self):
        card = ab.to_match_card([], now=NOW)
        schema_check.validate(card, self.root["definitions"]["Result"], self.root)
        self.assertFalse(card["payload"]["autoAssigned"])

    def test_reply_text_when_unrecognized(self):
        text = ab.build_reply_text(None)
        self.assertIn("再说得细一点", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
