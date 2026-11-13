import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
from v3_adapter import handle
from local_domains import DomainError


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.request = {
            "protocolVersion": "3.0", "userId": "test-user", "conversationId": "conv-test", "messageId": "msg-test",
            "task": {"id": "root-test", "parentTaskId": None, "version": 2, "invocationId": "invoke-test", "deadlineAt": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()},
            "input": {"text": "想学剪纸，别太远", "attachmentIds": []},
            "context": {"reason": "USER_MESSAGE", "history": []}
        }
        self.planner = Mock(return_value={"decision": "ASK", "reply": "在哪座城市？", "domains": ["culture"], "steps": [], "memoryCandidate": None})

    def test_question_has_program_id_but_no_server_owned_fields(self):
        result = handle(self.request, self.planner)
        self.assertEqual(result["data"]["taskId"], "root-test")
        self.assertEqual(result["data"]["baseTaskVersion"], 2)
        question = result["data"]["control"]["inputRequest"]
        self.assertEqual(uuid.UUID(question["inputRequestId"]).version, 4)
        self.assertNotIn("version", question)
        self.assertNotIn("ownerTaskId", question)

    def test_answer_preserves_original_need(self):
        self.request["context"].update(reason="INPUT_PROVIDED", inputResponse={"text": "长沙", "responseTo": {
            "ownerTaskId": "root-test", "inputRequestId": str(uuid.uuid4()), "version": 1, "selectedOptionId": None}})
        handle(self.request, self.planner)
        self.assertEqual(self.planner.call_args[0][0], "长沙")
        self.assertEqual(self.planner.call_args[0][1][-1]["content"], "想学剪纸，别太远")

    def test_expired_does_not_call_model(self):
        self.request["task"]["deadlineAt"] = "2020-01-01T00:00:00Z"
        self.assertEqual(handle(self.request, self.planner)["code"], "UPSTREAM_TIMEOUT")
        self.planner.assert_not_called()

    def test_invalid_nested_container_rejected_before_model(self):
        for key in ("task", "context", "input"):
            packet = dict(self.request)
            packet[key] = []
            self.assertEqual(handle(packet, self.planner)["code"], "INVALID_ARGUMENT")
        self.planner.assert_not_called()

    def test_child_answer_must_not_resume_root_plan(self):
        self.request["context"].update(reason="INPUT_PROVIDED", inputResponse={"text": "长沙", "responseTo": {
            "ownerTaskId": "child-test", "inputRequestId": str(uuid.uuid4()), "version": 1, "selectedOptionId": None}})
        self.assertEqual(handle(self.request, self.planner)["code"], "CAPABILITY_UNAVAILABLE")
        self.planner.assert_not_called()

    def test_unknown_recovery_does_not_reexecute(self):
        self.request["context"]["reason"] = "RECOVERY"
        self.request["context"]["actionLedger"]=[{"stepId":"s1","actionId":"a1","tool":"route.save","argsDigest":"x",
            "confirmationId":None,"executionStatus":"UNKNOWN","effectId":None,"businessRef":None,
            "externalStatus":None,"lastError":None,"retryPolicy":"RECONCILE_FIRST"}]
        self.assertEqual(handle(self.request, self.planner)["code"], "UPSTREAM_ERROR")
        self.planner.assert_not_called()

    def test_plan_does_not_invent_child_ids(self):
        self.planner.return_value["decision"] = "PLAN"
        self.assertEqual(handle(self.request, self.planner)["code"], "CAPABILITY_UNAVAILABLE")

    def test_plan_returns_real_child_ids_from_executor(self):
        self.planner.return_value = {"decision": "PLAN", "reply": "准备协作", "domains": ["culture"],
            "steps": [{"id": "s1", "agent": "a3", "domain": "culture", "goal": "查询剪纸课程", "dependsOn": []}],
            "memoryCandidate": None, "location": "长沙"}
        executor = Mock()
        executor.delegate_children.return_value = [{"childTaskId": "child-real-1", "status": "QUEUED"}]
        result = handle(self.request, self.planner, executor)
        self.assertEqual(result["code"], "OK")
        self.assertEqual(result["data"]["control"], {
            "next": "WAIT_DEPENDENCIES", "outcome": None,
            "dependencyTaskIds": ["child-real-1"], "inputRequest": None})
        executor.delegate_children.assert_called_once()

    def test_a1_tourism_plan_calls_real_domain_client_and_returns_v3_result(self):
        self.planner.return_value = {"decision": "PLAN", "reply": "准备查询", "domains": ["tourism"],
            "steps": [{"id": "s1", "agent": "a1", "domain": "tourism",
                       "goal": "查询西湖慢行建议", "dependsOn": []}],
            "memoryCandidate": None, "location": "杭州"}
        domain = Mock()
        domain.tourism.return_value = {"text": "西湖慢行建议已由8091返回。", "sources": [{"source": "AMAP"}]}
        self.request["input"]["text"] = "请介绍杭州西湖适合慢慢散步的地方"
        result = handle(self.request, self.planner, domain_client=domain)
        self.assertEqual(result["code"], "OK")
        self.assertEqual(result["data"]["control"]["outcome"], "SUCCEEDED")
        self.assertEqual(result["data"]["results"][0]["type"], "TOURISM_ADVICE")
        self.assertEqual(result["data"]["results"][0]["availability"], "REAL")
        self.assertIn("8091", result["data"]["reply"]["text"])
        domain.tourism.assert_called_once_with(self.request["input"]["text"], location="杭州")

    def test_a1_domain_failure_never_becomes_success(self):
        self.planner.return_value = {"decision": "PLAN", "reply": "准备查询", "domains": ["tourism"],
            "steps": [{"id": "s1", "agent": "a1", "domain": "tourism",
                       "goal": "查询", "dependsOn": []}], "memoryCandidate": None, "location": None}
        domain = Mock()
        domain.tourism.side_effect = DomainError("8091不可用")
        result = handle(self.request, self.planner, domain_client=domain)
        self.assertEqual(result["code"], "UPSTREAM_ERROR")
        self.assertIsNone(result["data"])

    def test_tourism_without_sources_requires_verification(self):
        self.planner.return_value = {"decision": "PLAN", "reply": "准备查询", "domains": ["tourism"],
            "steps": [{"id": "s1", "agent": "a1", "domain": "tourism",
                       "goal": "查询", "dependsOn": []}], "memoryCandidate": None, "location": None}
        domain = Mock()
        domain.tourism.return_value = {"text": "查询结果"}
        result = handle(self.request, self.planner, domain_client=domain)
        card = result["data"]["results"][0]
        self.assertEqual(card["availability"], "NEEDS_VERIFICATION")
        self.assertEqual(card["sources"], [])
        self.assertIn("未提供可核验来源", card["pendingChecks"][0])

    def test_tourism_reply_respects_v3_text_limit(self):
        self.planner.return_value = {"decision": "PLAN", "reply": "准备查询", "domains": ["tourism"],
            "steps": [{"id": "s1", "agent": "a1", "domain": "tourism",
                       "goal": "查询", "dependsOn": []}], "memoryCandidate": None, "location": None}
        domain = Mock()
        domain.tourism.return_value = {"text": "路" * 5000, "sources": [{"source": "AMAP"}]}
        result = handle(self.request, self.planner, domain_client=domain)
        self.assertEqual(len(result["data"]["reply"]["text"]), 4000)
        self.assertTrue(result["data"]["reply"]["text"].endswith("…"))

    def test_child_question_keeps_original_identity(self):
        question = {"inputRequestId": "9f75ab8a-73d4-4e26-909f-2f2e67b95d42", "ownerTaskId": "child-1", "version": 4,
                    "question": "想参加哪类文化活动？", "requiredFields": ["kind"], "options": [], "allowFreeText": True}
        self.request["context"].update(reason="CHILD_INPUT_REQUIRED", pendingInputRequests=[question],
            dependencyResults=[{"taskId": "child-1", "domain": "culture"}])
        result = handle(self.request, self.planner)
        self.assertEqual(result["data"]["control"]["inputRequest"]["inputRequestId"], "9f75ab8a-73d4-4e26-909f-2f2e67b95d42")
        self.assertNotIn("ownerTaskId", result["data"]["control"]["inputRequest"])
        self.planner.assert_not_called()

    def test_children_finished_integrates_without_replanning(self):
        self.request["context"].update(reason="CHILDREN_FINISHED", dependencyResults=[{
            "taskId":"child-1","parentTaskId":"root-test","targetAgent":"a3","domain":"culture",
            "required":True,"version":3,"status":"SUCCEEDED",
            "reply":{"text":"找到一项剪纸课程","speechRate":.8,"audioUrl":None},
            "results":[{"resultId":"result-1","type":"CULTURE","payload":{}}],
            "confirmationIds":[],"effectIds":[],"error":None,
            "completedAt":"2026-11-07T00:00:00Z","inputRequest":None}])
        result=handle(self.request,self.planner)
        self.assertEqual(result["data"]["control"]["outcome"],"SUCCEEDED")
        self.assertEqual(result["data"]["results"][0]["resultId"],"result-1")
        self.assertIn("剪纸课程",result["data"]["reply"]["text"])
        self.planner.assert_not_called()

    def test_child_confirmation_is_presented_without_replanning(self):
        self.request["context"].update(reason="CHILD_CONFIRMATION_REQUIRED",dependencyResults=[{
            "taskId":"child-1","parentTaskId":"root-test","targetAgent":"a2","domain":"care",
            "required":True,"version":3,"status":"WAITING_CONFIRMATION","reply":None,"results":[],
            "confirmationIds":["confirm-real-1"],"effectIds":[],"error":None,"completedAt":None,"inputRequest":None}])
        result=handle(self.request,self.planner)
        self.assertEqual(result["data"]["control"]["next"],"WAIT_CONFIRMATION")
        self.assertEqual(result["data"]["confirmationIds"],["confirm-real-1"])
        self.planner.assert_not_called()

    def test_confirmation_decided_uses_ledger_without_replanning(self):
        self.request["context"].update(reason="CONFIRMATION_DECIDED",confirmationResults=[{
            "confirmationId":"c1","ownerTaskId":"root-test","rootTaskId":"root-test","actionId":"a1",
            "version":2,"state":"EXECUTED","operation":"memory.change","summary":"保存少走路偏好",
            "expiresAt":"2026-11-07T01:00:00Z","actionStatus":"SUCCEEDED","lastError":None,"canRetry":False}],
            actionLedger=[{"stepId":"s1","actionId":"a1","tool":"memory.change","argsDigest":"x",
            "confirmationId":"c1","executionStatus":"SUCCEEDED","effectId":"e1","businessRef":None,
            "externalStatus":None,"lastError":None,"retryPolicy":"NO_RETRY"}])
        result=handle(self.request,self.planner)
        self.assertEqual(result["data"]["control"]["outcome"],"SUCCEEDED")
        self.assertIn("已执行",result["data"]["reply"]["text"])
        self.planner.assert_not_called()


if __name__ == "__main__": unittest.main()
