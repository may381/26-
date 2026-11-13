"""A3 非遗文化自测（文化课 DEMO 数据 · 筛选 · 排序 · 卡片 · 话术）。"""

from __future__ import annotations

import copy
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import schema_check  # noqa: E402
import v3_messages  # noqa: E402
from culture_courses import (  # noqa: E402
    AVAILABILITY_DEMO, DATASET_ID, DEMO_COURSES, KINDS, KIND_LABELS,
    build_reply_text, filter_courses, has_interest_info, kinds_from_interests,
    next_session, rank_courses, to_result_card,
)

NOW = datetime(2026, 10, 30, 8, 0, tzinfo=timezone.utc)      # 周五 08:00


def load_schema() -> dict:
    folder = v3_messages.schema_dir()
    assert folder, "找不到 control.schema.json"
    return schema_check.load_schema(os.path.join(folder, "control.schema.json"))


class DemoDatasetTest(unittest.TestCase):
    """假数据也要能过基本检查 —— 假不等于可以乱写。"""

    def test_every_course_has_required_fields(self):
        required = {"courseId", "kind", "title", "venue", "walkMinutes", "durationMin",
                    "weekdays", "timeOfDay", "level", "seatsLeft", "hasSteps",
                    "liftAvailable", "tags", "note"}
        for course in DEMO_COURSES:
            with self.subTest(course=course.get("courseId")):
                self.assertLessEqual(required, set(course))

    def test_course_ids_are_unique(self):
        ids = [c["courseId"] for c in DEMO_COURSES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_kinds_are_registered(self):
        for course in DEMO_COURSES:
            with self.subTest(course=course["courseId"]):
                self.assertIn(course["kind"], KINDS)
                self.assertIn(course["kind"], KIND_LABELS)

    def test_weekdays_are_iso_numbers(self):
        for course in DEMO_COURSES:
            with self.subTest(course=course["courseId"]):
                self.assertTrue(course["weekdays"])
                for day in course["weekdays"]:
                    self.assertIn(day, range(1, 8))

    def test_time_of_day_is_well_formed(self):
        for course in DEMO_COURSES:
            with self.subTest(course=course["courseId"]):
                hour, minute = course["timeOfDay"].split(":")
                self.assertIn(int(hour), range(24))
                self.assertIn(int(minute), range(60))

    def test_walk_and_duration_are_positive(self):
        for course in DEMO_COURSES:
            with self.subTest(course=course["courseId"]):
                self.assertGreater(course["walkMinutes"], 0)
                self.assertGreater(course["durationMin"], 0)


class InterestMappingTest(unittest.TestCase):
    """老人说"剪纸"，库里存 papercut，中间要有人翻译。"""

    def test_maps_chinese_to_kind(self):
        self.assertEqual(kinds_from_interests("喜欢剪纸"), ["papercut"])
        self.assertEqual(sorted(kinds_from_interests("喜欢剪纸和刺绣")),
                         ["embroidery", "papercut"])

    def test_maps_aliases(self):
        self.assertEqual(kinds_from_interests("爱剪窗花"), ["papercut"])
        self.assertEqual(kinds_from_interests("打太极拳"), ["taichi"])
        self.assertEqual(kinds_from_interests("爱听京剧"), ["opera"])

    def test_accepts_list(self):
        self.assertIn("papercut", kinds_from_interests(["喜欢剪纸", "腿脚不好"]))

    def test_unknown_returns_empty(self):
        self.assertEqual(kinds_from_interests("喜欢跳伞"), [])
        self.assertEqual(kinds_from_interests(""), [])
        self.assertEqual(kinds_from_interests(None), [])

    def test_has_interest_info_separates_two_cases(self):
        self.assertFalse(has_interest_info(None))
        self.assertFalse(has_interest_info(""))
        self.assertFalse(has_interest_info("   "))
        self.assertFalse(has_interest_info([]))
        self.assertTrue(has_interest_info("喜欢跳伞"))
        self.assertTrue(has_interest_info(["喜欢剪纸"]))


class FilterTest(unittest.TestCase):
    """筛 —— 只答"能不能去"，不管"好不好"。"""

    def ids(self, courses):
        return [c["courseId"] for c in courses]

    def test_interest_filters_by_kind(self):
        picked = filter_courses(DEMO_COURSES, interests="喜欢剪纸")
        self.assertTrue(picked)
        self.assertTrue(all(c["kind"] == "papercut" for c in picked))

    def test_walk_limit_excludes_far_ones(self):
        picked = filter_courses(DEMO_COURSES, interests="喜欢剪纸", max_walk_minutes=10)
        self.assertTrue(all(c["walkMinutes"] <= 10 for c in picked))
        self.assertNotIn("demo-papercut-02", self.ids(picked))   # 走 18 分钟

    def test_duration_limit_excludes_long_ones(self):
        picked = filter_courses(DEMO_COURSES, interests="戏曲", max_duration_min=120)
        self.assertEqual(picked, [], "京剧票友会 150 分钟，超了 2 小时就该排除")

    def test_step_free_excludes_stairs(self):
        picked = filter_courses(DEMO_COURSES, need_step_free=True)
        self.assertTrue(all(not c["hasSteps"] for c in picked))
        self.assertNotIn("demo-papercut-02", self.ids(picked))

    def test_zero_seats_excluded_by_default(self):
        picked = filter_courses(DEMO_COURSES, interests="民乐")
        self.assertEqual(picked, [], "二胡班名额为 0")
        relaxed = filter_courses(DEMO_COURSES, interests="民乐", only_with_seats=False)
        self.assertEqual(self.ids(relaxed), ["demo-folk-01"])

    def test_exclude_kinds(self):
        picked = filter_courses(DEMO_COURSES, exclude_kinds=["papercut"])
        self.assertFalse(any(c["kind"] == "papercut" for c in picked))

    def test_none_limits_mean_no_limit(self):
        picked = filter_courses(DEMO_COURSES, max_walk_minutes=None,
                                max_duration_min=None, only_with_seats=False)
        self.assertEqual(len(picked), len(DEMO_COURSES))

    def test_known_interest_with_no_match_returns_empty(self):
        """最要紧的一条：不能拿不相关的课凑数。"""
        self.assertEqual(filter_courses(DEMO_COURSES, interests="喜欢跳伞"), [])

    def test_unknown_interest_info_returns_all(self):
        """反过来的另一条：完全不知道偏好时，先全给。"""
        picked = filter_courses(DEMO_COURSES, interests=None)
        self.assertGreater(len(picked), 0)

    def test_does_not_mutate_input(self):
        snapshot = copy.deepcopy(DEMO_COURSES)
        filter_courses(DEMO_COURSES, interests="剪纸")
        rank_courses(DEMO_COURSES, interests="剪纸")
        self.assertEqual(DEMO_COURSES, snapshot)


class RankTest(unittest.TestCase):
    """排 —— 决定先给老人看哪个。"""

    def test_interest_match_comes_first(self):
        ranked = rank_courses(DEMO_COURSES, interests="刺绣")
        self.assertEqual(ranked[0]["kind"], "embroidery")

    def test_closer_wins_within_same_interest(self):
        ranked = rank_courses(
            [c for c in DEMO_COURSES if c["kind"] == "papercut"], interests="剪纸")
        walks = [c["walkMinutes"] for c in ranked]
        self.assertEqual(walks, sorted(walks))

    def test_step_free_gets_bonus(self):
        pair = rank_courses(DEMO_COURSES, interests="剪纸")
        step_free = next(c for c in pair if not c["hasSteps"])
        with_steps = next(c for c in pair if c["hasSteps"])
        self.assertGreater(step_free["score"], with_steps["score"] - 20)

    def test_reasons_are_human_readable(self):
        ranked = rank_courses(DEMO_COURSES, interests="剪纸")
        self.assertTrue(ranked[0]["reasons"])
        for reason in ranked[0]["reasons"]:
            self.assertIsInstance(reason, str)
            self.assertTrue(reason)

    def test_deterministic(self):
        first = [c["courseId"] for c in rank_courses(DEMO_COURSES, interests="剪纸")]
        second = [c["courseId"] for c in rank_courses(DEMO_COURSES, interests="剪纸")]
        self.assertEqual(first, second)

    def test_score_matches_sort_order(self):
        ranked = rank_courses(DEMO_COURSES, interests="剪纸")
        scores = [c["score"] for c in ranked]
        self.assertEqual(scores, sorted(scores, reverse=True))


class NextSessionTest(unittest.TestCase):
    """排期现算，不写死日期 —— 这样演示时永远不过期。"""

    def course(self, weekdays, time_of_day="09:00"):
        return {"weekdays": weekdays, "timeOfDay": time_of_day, "durationMin": 90}

    def test_same_day_future_time(self):
        session = next_session(self.course([5]), NOW)          # NOW 是周五 08:00
        self.assertEqual(session["startAt"], "2026-10-30T09:00:00Z")
        self.assertEqual(session["weekdayLabel"], "周五")

    def test_today_passed_time_rolls_to_next_week(self):
        session = next_session(self.course([5], "07:00"), NOW)  # 07:00 已过
        self.assertEqual(session["startAt"], "2026-11-06T07:00:00Z")

    def test_picks_nearest_upcoming_weekday(self):
        session = next_session(self.course([1, 4]), NOW)        # 周一或周四
        self.assertEqual(session["startAt"], "2026-11-02T09:00:00Z")   # 下周一是最近的

    def test_end_at_equals_start_plus_duration(self):
        session = next_session(self.course([5], "09:00"), NOW)
        start = datetime.fromisoformat(session["startAt"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(session["endAt"].replace("Z", "+00:00"))
        self.assertEqual((end - start), timedelta(minutes=90))

    def test_never_expires(self):
        """同一个课，一年后再看，仍然算得出下一次。"""
        course = self.course([4], "09:30")
        for shift in (0, 90, 365, 1000):
            with self.subTest(days=shift):
                session = next_session(course, NOW + timedelta(days=shift))
                self.assertIsNotNone(session["startAt"])
                start = datetime.fromisoformat(session["startAt"].replace("Z", "+00:00"))
                self.assertGreater(start, NOW + timedelta(days=shift) - timedelta(seconds=1))

    def test_naive_datetime_is_treated_as_utc(self):
        session = next_session(self.course([5]), datetime(2026, 10, 30, 8, 0))
        self.assertEqual(session["startAt"], "2026-10-30T09:00:00Z")


class ResultCardTest(unittest.TestCase):
    """卡片 —— P2 直接转给前端的形状。"""

    @classmethod
    def setUpClass(cls):
        cls.root = load_schema()
        cls.courses = rank_courses(filter_courses(DEMO_COURSES, interests="剪纸和刺绣"),
                                   interests="剪纸和刺绣")

    def card(self, **kwargs):
        base = {"now": NOW, "query": {"interests": "剪纸和刺绣"}}
        base.update(kwargs)
        return to_result_card(self.courses, **base)

    def test_passes_official_result_schema(self):
        schema_check.validate(self.card(), self.root["definitions"]["Result"], self.root)

    def test_availability_is_demo_not_real(self):
        self.assertEqual(self.card()["availability"], AVAILABILITY_DEMO)
        self.assertNotEqual(self.card()["availability"], "REAL")

    def test_business_ref_is_null(self):
        """假课程编一个业务 ID，P2 真去查就会 404。"""
        self.assertIsNone(self.card()["businessRef"])

    def test_sources_declare_demo_dataset(self):
        source = self.card()["sources"][0]
        self.assertEqual(source["type"], "DEMO_DATASET")
        self.assertEqual(source["id"], DATASET_ID)
        self.assertIn("虚构", source["note"])

    def test_pending_checks_warn_about_booking(self):
        checks = " ".join(self.card()["pendingChecks"])
        self.assertIn("演示", checks)
        self.assertIn("报名", checks)

    def test_read_only_and_not_booked(self):
        payload = self.card()["payload"]
        self.assertTrue(payload["readOnly"])
        self.assertFalse(payload["booked"])
        self.assertFalse(payload["notified"])

    def test_no_action_id_in_payload(self):
        """只查不报名：卡片里不能出现任何"去做"的句柄。"""
        text = str(self.card()["payload"])
        self.assertNotIn("actionId", text)
        self.assertNotIn("confirmationId", text)

    def test_limit_is_respected(self):
        self.assertEqual(self.card(limit=1)["payload"]["totalCandidates"], 1)
        self.assertEqual(len(self.card(limit=1)["payload"]["courses"]), 1)

    def test_result_id_is_stable_for_same_input(self):
        self.assertEqual(self.card()["resultId"], self.card()["resultId"])

    def test_result_id_changes_with_courses(self):
        few = self.card(limit=1)["resultId"]
        many = self.card(limit=3)["resultId"]
        self.assertNotEqual(few, many)

    def test_empty_result_still_valid_card(self):
        card = to_result_card([], now=NOW)
        schema_check.validate(card, self.root["definitions"]["Result"], self.root)
        self.assertEqual(card["availability"], AVAILABILITY_DEMO)
        self.assertEqual(card["payload"]["totalCandidates"], 0)
        self.assertIn("没找到", card["title"])

    def test_every_course_has_next_session(self):
        for item in self.card()["payload"]["courses"]:
            with self.subTest(course=item["courseId"]):
                self.assertIsNotNone(item["nextSession"]["startAt"])
                self.assertIsNotNone(item["nextSession"]["weekdayLabel"])

    def test_item_fields_are_frontend_friendly(self):
        item = self.card()["payload"]["courses"][0]
        for name in ("courseId", "title", "kindLabel", "venue", "walkMinutes",
                     "hasSteps", "nextSession", "reasons"):
            with self.subTest(field=name):
                self.assertIn(name, item)


class ReplyTextTest(unittest.TestCase):
    """说给老人听的话。短、具体、有下一步。"""

    def test_empty_case_does_not_blame_user(self):
        text = build_reply_text([], now=NOW)
        self.assertIn("没找到", text)
        self.assertIn("再帮您找", text)
        self.assertNotIn("您没有", text)

    def test_single_result_mentions_venue_and_time(self):
        course = next(c for c in DEMO_COURSES if c["courseId"] == "demo-papercut-01")
        text = build_reply_text([course], now=NOW)
        self.assertIn("阳光社区活动室", text)
        self.assertIn("5 分钟", text)
        self.assertIn("周四", text)

    def test_multiple_results_offer_next_step(self):
        courses = rank_courses(DEMO_COURSES, interests="剪纸", max_walk_minutes=30)
        text = build_reply_text(courses, now=NOW)
        self.assertIn("找到", text)
        self.assertIn("备选", text)

    def test_time_is_spoken_chinese(self):
        papercut = next(c for c in DEMO_COURSES if c["timeOfDay"] == "09:30")
        self.assertIn("上午九点半", build_reply_text([papercut], now=NOW))

    def test_afternoon_time_uses_afternoon(self):
        opera = next(c for c in DEMO_COURSES if c["timeOfDay"] == "14:30")
        text = build_reply_text([opera], now=NOW)
        self.assertIn("下午", text)
        self.assertIn("两点半", text)
        self.assertNotIn("十四点", text)

    def test_reply_fits_elderly_attention(self):
        courses = rank_courses(DEMO_COURSES, interests="剪纸", max_walk_minutes=30)
        self.assertLessEqual(len(build_reply_text(courses, now=NOW)), 120)


class EndToEndTest(unittest.TestCase):
    """整条路走一遍：记忆 → 筛选 → 排序 → 卡片 + 话术 → 装进 v3 响应。"""

    def test_full_flow_produces_valid_agent_response(self):
        root = load_schema()
        body = {
            "protocolVersion": "3.0", "userId": "u100", "conversationId": "conv-001",
            "messageId": "msg-001",
            "task": {"id": "child-003", "parentTaskId": "root-001", "version": 2,
                     "attempt": 1, "invocationId": "invoke-child-003",
                     "deadlineAt": "2030-10-29T02:01:00Z"},
            "input": {"text": "想学剪纸，走路别太远", "attachmentIds": []},
            "context": {"businessRefs": [], "history": [], "completedEffects": [],
                        "reason": "USER_MESSAGE", "candidateTasks": [],
                        "dependencyResults": [], "confirmationResults": [],
                        "actionLedger": [], "planSteps": [],
                        "readSet": {"memoryRevision": 7, "authorizationRevision": 3,
                                    "provenanceRefs": []},
                        "inputResponse": None, "pendingInputRequests": []},
            "capabilityToken": "DEMO-TOKEN-NOT-A-REAL-CREDENTIAL",
        }
        inv = v3_messages.parse_invocation(body, root_schema=root)

        interests = "喜欢剪纸"                       # 本该来自 memory.search
        courses = rank_courses(
            filter_courses(DEMO_COURSES, interests=interests, max_walk_minutes=15),
            interests=interests)
        card = to_result_card(courses, now=NOW, query={"interests": interests})
        reply = build_reply_text(courses, now=NOW)

        response = v3_messages.build_response(
            inv, intent="culture", domains=["culture"], reply_text=reply,
            next_step=v3_messages.NEXT_COMPLETE,
            outcome=v3_messages.OUTCOME_SUCCEEDED,
            results=[card],
            used_memory_refs=[{"memoryId": "memory-004", "version": 1}],
            available_memories=[{"memoryId": "memory-004", "version": 1}],
            root_schema=root)

        schema_check.validate(response, root["definitions"]["AgentResponse"], root)
        self.assertEqual(response["data"]["results"][0]["availability"], "DEMO")
        self.assertIn("剪纸", response["data"]["reply"]["text"])

    def test_same_flow_with_no_memories_still_answers(self):
        """记忆服务挂了也要能给答案 —— 只是没那么个性化。"""
        courses = rank_courses(filter_courses(DEMO_COURSES, interests=None),
                               interests=None)[:2]
        card = to_result_card(courses, now=NOW)
        self.assertEqual(card["availability"], "DEMO")
        self.assertTrue(build_reply_text(courses, now=NOW))


if __name__ == "__main__":
    unittest.main(verbosity=2)
