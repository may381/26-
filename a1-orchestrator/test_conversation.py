import copy
import json
import unittest
from unittest.mock import Mock
from a1 import Conversation, PlanningError, enforce_location


def travel(location=None):
    return {"decision": "PLAN", "reply": "准备查询", "domains": ["tourism"],
            "steps": [{"id": "s1", "agent": "a1", "domain": "tourism",
                       "goal": "查询旅游建议", "dependsOn": []}],
            "memoryCandidate": None, "location": location}


class LocationAndConversationTests(unittest.TestCase):
    def test_outing_then_hangzhou(self):
        planner = Mock(side_effect=[travel(), travel("杭州")])
        session = Conversation(planner)
        first = session.turn("想出去玩")
        self.assertEqual(first["decision"], "ASK")
        self.assertEqual(first["steps"], [])
        self.assertIn("城市", first["reply"])
        second = session.turn("杭州")
        self.assertEqual(second["decision"], "PLAN")
        self.assertEqual(second["location"], "杭州")
        self.assertEqual(planner.call_args.args[1][0], {"role": "user", "content": "想出去玩"})
        self.assertEqual(len(session.history), 4)
        self.assertEqual(json.loads(session.history[1]["content"]), first)

    def test_invented_shanghai_rejected_even_after_hangzhou(self):
        history = [{"role": "user", "content": "想出去玩"},
                   {"role": "assistant", "content": "建议上海"}]
        original = travel("上海"); before = copy.deepcopy(original)
        result = enforce_location(original, "杭州", history)
        self.assertEqual(result["decision"], "ASK")
        self.assertIsNone(result["location"])
        self.assertEqual(result["steps"], [])
        self.assertEqual(original, before)

    def test_location_in_previous_user_message_is_valid(self):
        history = [{"role": "user", "content": "想在杭州出去玩，少走路"}]
        self.assertEqual(enforce_location(travel("杭州"), "两天", history)["decision"], "PLAN")

    def test_system_and_tool_locations_are_not_evidence(self):
        for role in ("assistant", "system", "tool"):
            with self.subTest(role=role):
                result = enforce_location(travel("上海"), "想出去玩", [{"role": role, "content": "上海"}])
                self.assertEqual(result["decision"], "ASK")

    def test_location_must_be_contiguous_original_text(self):
        self.assertEqual(enforce_location(travel("杭州市"), "杭州旅游")["decision"], "ASK")
        self.assertEqual(enforce_location(travel("杭州西湖"), "杭州的西湖旅游")["decision"], "ASK")

    def test_non_location_reply_clears_invented_location(self):
        value = {"decision": "REPLY", "reply": "您好", "domains": [], "steps": [],
                 "memoryCandidate": None, "location": "上海"}
        result = enforce_location(value, "你好")
        self.assertIsNone(result["location"])
        self.assertEqual(result["decision"], "REPLY")
        self.assertEqual(value["location"], "上海")

    def test_fraud_plan_does_not_require_location(self):
        value = travel(); value["domains"] = ["fraud"]; value["steps"][0]["domain"] = "fraud"
        self.assertEqual(enforce_location(value, "请分析退款短信")["decision"], "PLAN")

    def test_missing_location_clears_memory_candidate_on_ask(self):
        value = travel("上海"); value["memoryCandidate"] = "喜欢旅游"
        result = enforce_location(value, "想出去玩")
        self.assertIsNone(result["memoryCandidate"])

    def test_failure_preserves_existing_history_and_last_plan(self):
        planner = Mock(return_value=travel("杭州")); session = Conversation(planner)
        session.turn("杭州旅游")
        before = copy.deepcopy((session.history, session.last_plan))
        for failure in (PlanningError("模型不可达"), {"invalid": True}):
            planner.side_effect = failure if isinstance(failure, Exception) else None
            planner.return_value = failure
            with self.assertRaises(PlanningError): session.turn("两天")
            self.assertEqual((session.history, session.last_plan), before)

    def test_planner_cannot_pollute_history_or_invent_evidence(self):
        session = Conversation(lambda text, history: travel())
        session.turn("想出去玩")
        before = copy.deepcopy((session.history, session.last_plan))
        def failing(text, history):
            history[0]["content"] = "上海"
            history.append({"role": "user", "content": "上海"})
            raise PlanningError("失败")
        session.planner = failing
        with self.assertRaises(PlanningError): session.turn("杭州")
        self.assertEqual((session.history, session.last_plan), before)
        def inventing(text, history):
            history.append({"role": "user", "content": "上海"})
            return travel("上海")
        session.planner = inventing
        self.assertEqual(session.turn("杭州")["decision"], "ASK")

    def test_returned_plan_cannot_mutate_last_plan(self):
        session = Conversation(lambda text, history: travel("杭州"))
        result = session.turn("杭州旅游")
        result["steps"][0]["goal"] = "修改"
        self.assertEqual(session.last_plan["steps"][0]["goal"], "查询旅游建议")

    def test_twelve_round_limit_without_dropping_history(self):
        planner = Mock(return_value={"decision": "REPLY", "reply": "您好", "domains": [],
                                    "steps": [], "memoryCandidate": None})
        session = Conversation(planner)
        for _ in range(12): session.turn("你好")
        self.assertEqual(len(session.history), 24)
        before = copy.deepcopy(session.history)
        with self.assertRaisesRegex(PlanningError, "已达12轮"): session.turn("继续")
        self.assertEqual(planner.call_count, 12)
        self.assertEqual(session.history, before)
        session.reset()
        self.assertEqual(session.history, [])
        self.assertIsNone(session.last_plan)
        session.turn("你好")
        self.assertEqual(len(session.history), 2)

    def test_invalid_input_never_calls_planner(self):
        planner = Mock(); session = Conversation(planner)
        for text in (None, "", "  ", "字" * 2001):
            with self.subTest(text=text), self.assertRaises(PlanningError): session.turn(text)
        planner.assert_not_called()
        self.assertEqual(session.history, [])


if __name__ == "__main__": unittest.main()
