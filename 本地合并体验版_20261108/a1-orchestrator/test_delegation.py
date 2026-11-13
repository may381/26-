"""委派第一步的契约测试：要么发出合规报文，要么什么都不发。"""
import os
import unittest
from unittest.mock import patch

from delegation import register_delegation_step
from p2_client import P2Client, P2Error


class RecordingP2(P2Client):
    def __init__(self):
        super().__init__(transport=lambda *a, **k: '{"code":"OK","message":"ok","data":{"steps":[{"clientStepKey":"s1","stepId":"step-1"}]}}',
                         base="http://127.0.0.1:8080", key="k" * 32)
        self.sent = []

    def register_steps(self, task_id, request_key, plan_version, steps, idempotency_key=None):
        self.sent.append({"task": task_id, "requestKey": request_key,
                          "planVersion": plan_version, "steps": steps})
        return {"steps": [{"clientStepKey": "s1", "stepId": "step-1"}]}


class DelegationStepTests(unittest.TestCase):
    def setUp(self):
        self.p2 = RecordingP2()

    def test_missing_tool_refuses_without_sending(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("A1_DELEGATE_TOOL", None)
            with self.assertRaises(P2Error) as error:
                register_delegation_step(self.p2, task_id="t1", plan_version=1, request_key="r1")
        self.assertIn("A1_DELEGATE_TOOL", str(error.exception))
        self.assertEqual(self.p2.sent, [])

    def test_env_configures_tool(self):
        with patch.dict(os.environ, {"A1_DELEGATE_TOOL": "agent.delegate"}):
            data = register_delegation_step(self.p2, task_id="t1", plan_version=2, request_key="r1")
        self.assertEqual(data["steps"][0]["stepId"], "step-1")
        sent = self.p2.sent[0]
        self.assertEqual(sent["planVersion"], 2)
        self.assertEqual(sent["steps"], [{"clientStepKey": "s1", "tool": "agent.delegate", "args": {}}])

    def test_explicit_tool_overrides_env(self):
        register_delegation_step(self.p2, task_id="t1", plan_version=1, request_key="r1",
                                 tool="care.request", args={"goal": "陪诊"})
        self.assertEqual(self.p2.sent[0]["steps"][0]["tool"], "care.request")
        self.assertEqual(self.p2.sent[0]["steps"][0]["args"], {"goal": "陪诊"})

    def test_args_must_be_object(self):
        with self.assertRaises(P2Error):
            register_delegation_step(self.p2, task_id="t1", plan_version=1, request_key="r1",
                                     tool="agent.delegate", args=["not", "object"])
        self.assertEqual(self.p2.sent, [])

    def test_step_key_length_is_checked(self):
        with self.assertRaises(P2Error):
            register_delegation_step(self.p2, task_id="t1", plan_version=1, request_key="r1",
                                     tool="agent.delegate", client_step_key="x" * 129)
        self.assertEqual(self.p2.sent, [])


if __name__ == "__main__":
    unittest.main()
