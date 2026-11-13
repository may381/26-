"""学习记录自测（计划是建议、进度是解读、出勤是 P2 的事实）。"""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import learning_record as lr  # noqa: E402
import schema_check  # noqa: E402
import v3_messages  # noqa: E402

NOW = datetime(2026, 11, 9, 8, 0, tzinfo=timezone.utc)
COURSE = {"courseId": "demo-papercut-01", "title": "剪纸入门班",
          "venue": "阳光社区活动室", "walkMinutes": 5, "durationMin": 90}


class BuildPlanTest(unittest.TestCase):
    def test_plan_starts_as_draft(self):
        """计划是建议，不能直接置为生效。"""
        plan = lr.build_plan(COURSE, weekly_times=2, now=NOW)
        self.assertEqual(plan["state"], lr.PLAN_DRAFT)

    def test_planned_minutes_is_duration_times_sessions(self):
        plan = lr.build_plan(COURSE, weekly_times=2, total_sessions=10, now=NOW)
        self.assertEqual(plan["plannedTotalMinutes"], 900)

    def test_default_sessions_eight_weeks(self):
        plan = lr.build_plan(COURSE, weekly_times=1, now=NOW)
        self.assertEqual(plan["totalSessions"], 8)

    def test_requires_course_id(self):
        with self.assertRaises(lr.LearningRecordError):
            lr.build_plan({"title": "无编号课程"})

    def test_weekly_times_bounds(self):
        for bad in (0, 8, -1):
            with self.subTest(bad=bad):
                with self.assertRaises(lr.LearningRecordError):
                    lr.build_plan(COURSE, weekly_times=bad)

    def test_zip_duration_rejected(self):
        with self.assertRaises(lr.LearningRecordError):
            lr.build_plan({"courseId": "x", "durationMin": 0})

    def test_plan_id_stable(self):
        a = lr.build_plan(COURSE, weekly_times=2, now=NOW)
        b = lr.build_plan(COURSE, weekly_times=2, now=NOW)
        self.assertEqual(a["planId"], b["planId"])


class SummarizeTest(unittest.TestCase):
    def setUp(self):
        self.plan = lr.build_plan(COURSE, weekly_times=2, total_sessions=16, now=NOW)

    def test_no_records_means_no_records(self):
        """没有打卡记录就说没有，不能按计划倒推出勤。"""
        s = lr.summarize_progress(self.plan, [], now=NOW)
        self.assertFalse(s["hasRecords"])
        self.assertEqual(s["dataOrigin"], "NO_RECORDS")
        self.assertEqual(s["attendedCount"], 0)
        self.assertIn("还没有打卡记录", s["summaryText"])

    def test_actual_minutes_only_from_attended(self):
        sessions = [{"durationMin": 90, "status": lr.ATTENDED},
                    {"durationMin": 90, "status": lr.ATTENDED},
                    {"durationMin": 0, "status": lr.ABSENT}]
        s = lr.summarize_progress(self.plan, sessions, now=NOW)
        self.assertEqual(s["attendedCount"], 2)
        self.assertEqual(s["actualMinutes"], 180)
        self.assertNotEqual(s["actualMinutes"], self.plan["plannedTotalMinutes"])

    def test_data_origin_declared(self):
        sessions = [{"durationMin": 90, "status": lr.ATTENDED}]
        s = lr.summarize_progress(self.plan, sessions, now=NOW)
        self.assertEqual(s["dataOrigin"], "P2_ATTENDANCE_RECORDS")

    def test_completion_percent(self):
        sessions = [{"durationMin": 90, "status": lr.ATTENDED}] * 4
        s = lr.summarize_progress(self.plan, sessions, now=NOW)
        self.assertEqual(s["completionPercent"], 25)
        self.assertEqual(s["remainingSessions"], 12)

    def test_all_absent_gives_actionable_text(self):
        s = lr.summarize_progress(self.plan, [{"status": lr.ABSENT}] * 2, now=NOW)
        self.assertIn("调整", s["summaryText"])

    def test_too_many_records_rejected(self):
        with self.assertRaises(lr.LearningRecordError):
            lr.summarize_progress(self.plan, [{"status": lr.ABSENT}] * 300)

    def test_missing_plan_id_rejected(self):
        with self.assertRaises(lr.LearningRecordError):
            lr.summarize_progress({}, [])


class CardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        folder = v3_messages.schema_dir()
        cls.root = schema_check.load_schema(os.path.join(folder, "control.schema.json"))

    def test_plan_card_valid(self):
        plan = lr.build_plan(COURSE, weekly_times=1, now=NOW)
        card = lr.to_plan_card(plan, now=NOW)
        schema_check.validate(card, self.root["definitions"]["Result"], self.root)
        self.assertTrue(card["payload"]["confirmRequired"])

    def test_progress_card_valid(self):
        plan = lr.build_plan(COURSE, weekly_times=1, now=NOW)
        summary = lr.summarize_progress(plan, [], now=NOW)
        card = lr.to_progress_card(summary, now=NOW)
        schema_check.validate(card, self.root["definitions"]["Result"], self.root)
        self.assertEqual(card["availability"], "DEMO")

    def test_progress_card_states_no_estimation(self):
        plan = lr.build_plan(COURSE, weekly_times=1, now=NOW)
        summary = lr.summarize_progress(plan, [], now=NOW)
        joined = " ".join(lr.to_progress_card(summary, now=NOW)["pendingChecks"])
        self.assertIn("不做估算", joined)


if __name__ == "__main__":
    unittest.main(verbosity=2)
