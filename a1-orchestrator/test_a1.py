import copy
import json
import unittest
from unittest.mock import patch, MagicMock
from a1 import validate_plan, ask_model, PlanningError, Conversation, enforce_location, SYSTEM


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.plan = {"decision": "PLAN", "reply": "先找课程，再整理陪同需要。",
                     "domains": ["culture", "care"], "memoryCandidate": None,
                     "steps": [{"id": "s1", "agent": "a3", "domain": "culture", "goal": "查课程", "dependsOn": []},
                               {"id": "s2", "agent": "a2", "domain": "care", "goal": "准备陪同方案", "dependsOn": ["s1"]}]}

    def test_cross_agent_plan(self):
        self.assertEqual(validate_plan(self.plan), self.plan)

    def test_wrong_owner_rejected(self):
        self.plan["steps"][0]["agent"] = "a2"
        with self.assertRaises(PlanningError): validate_plan(self.plan)

    def test_self_or_forward_dependency_rejected(self):
        self.plan["steps"][0]["dependsOn"] = ["s2"]
        with self.assertRaises(PlanningError): validate_plan(self.plan)

    def test_unregistered_execution_field_rejected(self):
        self.plan["executeUrl"] = "http://example.invalid/notify"
        with self.assertRaises(PlanningError): validate_plan(self.plan)

    def test_question_has_no_steps(self):
        p = {"decision": "ASK", "reply": "准备去哪座城市？", "domains": ["tourism"], "steps": [], "memoryCandidate": None}
        self.assertEqual(validate_plan(p)["decision"], "ASK")

    @patch("a1.urlopen")
    def test_real_client_payload_and_truncation(self, opened):
        response = MagicMock()
        response.read.return_value = json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(self.plan)}}]}).encode()
        opened.return_value.__enter__.return_value = response
        self.plan["location"] = "长沙"
        response.read.return_value = json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(self.plan)}}]}).encode()
        self.assertEqual(ask_model("在长沙找课程并找家属陪同"), self.plan)
        payload = json.loads(opened.call_args[0][0].data)
        self.assertEqual(payload["model"], "qwen3.8-27b")
        response.read.return_value = b'{"choices":[{"finish_reason":"length"}]}'
        with self.assertRaises(PlanningError): ask_model("需求")

    @patch("a1.urlopen")
    def test_nonfinal_model_plan_is_not_accepted(self, opened):
        response = MagicMock()
        opened.return_value.__enter__.return_value = response
        for reason in (None, "content_filter", "tool_calls"):
            response.read.return_value = json.dumps({"choices": [{"finish_reason": reason, "message": {"content": json.dumps(self.plan)}}]}).encode()
            with self.assertRaises(PlanningError): ask_model("长沙")

    @patch("a1.ask_model")
    def test_followup_keeps_original_request_and_reset_clears_it(self, model):
        question = {"decision": "ASK", "reply": "在哪座城市？", "domains": ["culture", "care"], "steps": [], "memoryCandidate": None}
        model.return_value = question
        session = Conversation()
        session.turn("想学剪纸，别太远，希望女儿陪同")
        model.return_value = self.plan
        self.plan["location"] = "长沙"
        session.turn("长沙")
        passed_history = model.call_args[0][1]
        self.assertIn("女儿陪同", passed_history[0]["content"])
        self.assertEqual(passed_history[1]["role"], "assistant")
        session.reset()
        self.assertEqual(session.history, [])
        self.assertIsNone(session.last_plan)

    def test_missing_location_overrides_model_plan(self):
        result = enforce_location(self.plan, "想学剪纸，别太远，希望女儿陪同")
        self.assertEqual(result["decision"], "ASK")
        self.assertEqual(result["steps"], [])

    def test_model_invented_location_cannot_bypass_gate(self):
        self.plan["location"] = "北京"
        result = enforce_location(self.plan, "想学剪纸，别太远")
        self.assertEqual(result["decision"], "ASK")

    def test_followup_user_location_allows_plan(self):
        self.plan["location"] = "长沙"
        history = [{"role": "user", "content": "想学剪纸，别太远，希望女儿陪同"}]
        self.assertEqual(enforce_location(self.plan, "长沙", history)["decision"], "PLAN")

    def test_new_trip_request_does_not_inherit_history_city(self):
        plan = copy.deepcopy(self.plan)
        plan.update(domains=["tourism"], location="杭州",
                    steps=[{"id": "s1", "agent": "a1", "domain": "tourism",
                            "goal": "查询杭州行程", "dependsOn": []}])
        history = [{"role": "user", "content": "我想去杭州玩三天"}]
        result = enforce_location(plan, "帮我规划出行", history)
        self.assertEqual(result["decision"], "ASK")
        self.assertIsNone(result["location"])

    def test_clarification_still_inherits_history_city(self):
        plan = copy.deepcopy(self.plan)
        plan.update(domains=["tourism"], location="杭州",
                    steps=[{"id": "s1", "agent": "a1", "domain": "tourism",
                            "goal": "查询杭州行程", "dependsOn": []}])
        history = [{"role": "user", "content": "我想去杭州玩三天"}]
        self.assertEqual(enforce_location(plan, "两天", history)["decision"], "PLAN")

    @patch("a1.ask_model")
    def test_failed_or_invalid_model_result_does_not_commit(self, model):
        session = Conversation()
        model.side_effect = PlanningError("超时")
        with self.assertRaises(PlanningError): session.turn("长沙")
        self.assertEqual(session.history, [])
        model.side_effect = None
        model.return_value = {"invalid": True}
        with self.assertRaises(PlanningError): session.turn("长沙")
        self.assertEqual(session.history, [])

    @patch("a1.urlopen")
    def test_followup_history_sent_to_real_http_payload(self, opened):
        response = MagicMock()
        response.read.return_value = json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(self.plan)}}]}).encode()
        opened.return_value.__enter__.return_value = response
        history = [{"role": "user", "content": "想学剪纸，女儿陪同"}, {"role": "assistant", "content": "在哪座城市？"}]
        ask_model("长沙", history)
        messages = json.loads(opened.call_args[0][0].data)["messages"]
        # 助手旧回复是自然语言，不能作为提示样例回灌给模型，否则模型会改写成 Markdown；
        # 只保留一个不含内容的固定标记来表示这一轮已经回复过。
        self.assertEqual(messages[1], history[0])
        self.assertEqual(messages[2], {"role": "assistant", "content": "（上一轮助手已回复，内容略）"})
        self.assertEqual(messages[-1]["content"], "长沙")
        self.assertNotIn("在哪座城市", json.dumps(messages, ensure_ascii=False))


class ModelClientTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict("os.environ", {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.plan = {"decision": "REPLY", "reply": "您好", "domains": [],
                     "steps": [], "memoryCandidate": None}

    def response(self, opened, raw=None):
        response = MagicMock()
        response.read.return_value = raw if raw is not None else json.dumps({"choices": [
            {"finish_reason": "stop", "message": {"content": json.dumps(self.plan)}}]}).encode()
        opened.return_value.__enter__.return_value = response
        return response

    @patch("a1.urlopen")
    def test_default_request_contract(self, opened):
        response = self.response(opened)
        history = [{"role": "user", "content": "你好"},
                   {"role": "assistant", "content": "您好"}]
        original = copy.deepcopy(history)
        self.assertEqual(ask_model("继续", history), self.plan)
        request = opened.call_args.args[0]
        self.assertEqual(request.full_url, "http://10.138.50.151:8000/v1/chat/completions")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(opened.call_args.kwargs, {"timeout": 40.0})
        response.read.assert_called_once_with(1024 * 1024 + 1)
        payload = json.loads(request.data)
        self.assertEqual(payload["model"], "qwen3.8-27b")
        # 只保留用户原话；助手回复只留固定标记，避免模型模仿成 Markdown 或把它当事实。
        self.assertEqual(payload["messages"], [{"role": "system", "content": SYSTEM}]
                         + [{"role": "user", "content": "你好"}]
                         + [{"role": "assistant", "content": "（上一轮助手已回复，内容略）"}]
                         + [{"role": "user", "content": "继续"}])
        self.assertEqual(history, original)

    @patch("a1.urlopen")
    def test_environment_origin_base_and_full_endpoint(self, opened):
        self.response(opened)
        for url in ("http://localhost:9999", "http://localhost:9999/v1/", "http://localhost:9999/v1/chat/completions"):
            with self.subTest(url=url), patch.dict("os.environ", {"A1_MODEL_URL": url, "A1_MODEL_NAME": "school-test"}):
                ask_model("你好")
                request = opened.call_args.args[0]
                self.assertEqual(request.full_url, "http://localhost:9999/v1/chat/completions")
                self.assertEqual(json.loads(request.data)["model"], "school-test")

    @patch("a1.urlopen")
    def test_non_json_output_is_retried_once(self, opened):
        def context(content):
            response = MagicMock()
            response.read.return_value = json.dumps({"choices": [
                {"finish_reason": "stop", "message": {"content": content}}]}
            ).encode()
            holder = MagicMock()
            holder.__enter__.return_value = response
            return holder

        opened.side_effect = [
            context("长沙适合老人的景点：\n1. 橘子洲\n2. 岳麓山"),
            context(json.dumps(self.plan)),
        ]
        self.assertEqual(ask_model("推荐长沙景点"), self.plan)
        self.assertEqual(opened.call_count, 2)
        messages = json.loads(opened.call_args_list[-1][0][0].data)["messages"]
        self.assertIn("格式纠正", messages[0]["content"])

    @patch("a1.urlopen")
    def test_hint_is_system_scoped_and_not_user_text(self, opened):
        self.response(opened)
        ask_model("长沙", [{"role": "user", "content": "帮我规划出行"}],
                  hint="上一轮提问：希望在哪座城市查找？")
        payload = json.loads(opened.call_args.args[0].data)
        system = payload["messages"][0]["content"]
        self.assertTrue(system.startswith(SYSTEM))
        self.assertIn("【本轮约束】", system)
        self.assertIn("上一轮提问", system)
        # 约束只进 system，不改变用户消息，也不进入地点证据。
        self.assertEqual(payload["messages"][-1], {"role": "user", "content": "长沙"})

    @patch("a1.urlopen")
    def test_oversized_response_rejected(self, opened):
        self.response(opened, b"x" * (1024 * 1024 + 1))
        with self.assertRaisesRegex(PlanningError, "^模型响应过大$"):
            ask_model("你好")

    @patch("a1.urlopen")
    def test_exact_response_limit_allowed(self, opened):
        response = self.response(opened)
        raw = response.read.return_value
        response.read.return_value = raw + b" " * (1024 * 1024 - len(raw))
        self.assertEqual(ask_model("你好"), self.plan)

    @patch("a1.urlopen")
    def test_invalid_responses_hide_raw_content(self, opened):
        for raw in (b"upstream-secret", b"{}", b"[]", b"\xff", b'{"choices":[]}'):
            with self.subTest(raw=raw):
                self.response(opened, raw)
                with self.assertRaises(PlanningError) as caught:
                    ask_model("你好")
                self.assertTrue(str(caught.exception).startswith("模型调用或计划解析失败（"))
                self.assertNotIn("upstream-secret", str(caught.exception))

    @patch("a1.urlopen", side_effect=TimeoutError("secret-provider-url"))
    def test_network_error_is_sanitized(self, opened):
        with self.assertRaises(PlanningError) as caught:
            ask_model("你好")
        self.assertEqual(str(caught.exception), "模型调用或计划解析失败（TimeoutError），未执行任何业务")

    @patch("a1.urlopen")
    def test_serialization_failure_is_planning_error(self, opened):
        with self.assertRaises(PlanningError) as caught:
            ask_model(object())
        self.assertEqual(str(caught.exception), "模型调用或计划解析失败（TypeError），未执行任何业务")
        opened.assert_not_called()

    @patch("a1.urlopen")
    def test_invalid_plan_and_invented_location_are_gated(self, opened):
        self.plan["executeUrl"] = "http://invalid.example"
        self.response(opened)
        with self.assertRaisesRegex(PlanningError, "^模型计划字段不符合约定$"):
            ask_model("你好")
        self.plan = {"decision": "PLAN", "reply": "查附近景点", "domains": ["tourism"],
                     "steps": [{"id": "s1", "agent": "a1", "domain": "tourism", "goal": "查询", "dependsOn": []}],
                     "location": "北京", "memoryCandidate": None}
        self.response(opened)
        self.assertEqual(ask_model("附近旅游")["decision"], "ASK")


if __name__ == "__main__": unittest.main()
