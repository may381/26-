"""P2 出站客户端的契约测试：不发真实请求，只验证"该发什么、不该发什么"。"""
import json
import unittest

from p2_client import P2Client, P2Error


def envelope(data=None, code="OK", message="成功"):
    return json.dumps({"code": code, "message": message, "data": data}, ensure_ascii=False)


class RecordingTransport:
    def __init__(self, reply=None, raises=None):
        self.calls = []
        self.reply = reply if reply is not None else envelope({"ok": True})
        self.raises = raises

    def __call__(self, method, path, body, headers):
        self.calls.append({"method": method, "path": path, "body": body, "headers": dict(headers)})
        if self.raises:
            raise self.raises
        return self.reply


def client(transport, key="k" * 32, context_token="context-token-1"):
    return P2Client(transport=transport, base="http://127.0.0.1:8080", key=key,
                    context_token=context_token)


class ContractTests(unittest.TestCase):
    def test_delegation_matches_schema_required_fields(self):
        t = RecordingTransport()
        client(t).delegate("conv-1", "task-1", "act-1", {"goal": "查长沙课程"})
        call = t.calls[0]
        self.assertEqual(call["method"], "POST")
        self.assertEqual(call["path"], "/internal/agent/v3/delegations")
        self.assertEqual(set(call["body"]), {"protocolVersion", "conversationId", "taskId", "actionId", "input"})
        self.assertEqual(call["body"]["protocolVersion"], "3.0")
        self.assertEqual(call["headers"]["X-Agent-Key"], "k" * 32)

    def test_steps_path_contains_task_and_keeps_request_key(self):
        t = RecordingTransport()
        client(t).register_steps("task-9", "req-key-1", 2, [{"stepId": "s1"}])
        call = t.calls[0]
        self.assertEqual(call["path"], "/internal/agent/v3/tasks/task-9/steps")
        self.assertEqual(call["body"]["requestKey"], "req-key-1")
        self.assertEqual(call["body"]["planVersion"], 2)

    def test_action_requires_idempotency_key_before_network(self):
        t = RecordingTransport()
        with self.assertRaises(P2Error):
            client(t).prepare_action("task-1", "step-1", {"tool": "memory.search"}, idempotency_key="")
        self.assertEqual(t.calls, [])

    def test_action_sends_idempotency_header(self):
        t = RecordingTransport()
        client(t).prepare_action("task-1", "step-1", {"tool": "memory.search"}, idempotency_key="idem-1")
        self.assertEqual(t.calls[0]["path"], "/internal/agent/v3/actions")
        self.assertEqual(t.calls[0]["headers"]["Idempotency-Key"], "idem-1")

    def test_confirmation_returns_data_envelope(self):
        t = RecordingTransport(reply=envelope({"confirmationId": "c-1"}))
        data = client(t).prepare_confirmation("task-1", "act-1")
        self.assertEqual(data, {"confirmationId": "c-1"})
        self.assertEqual(t.calls[0]["path"], "/internal/agent/v3/confirmations")

    def test_tool_execution_matches_protocol_template(self):
        t = RecordingTransport(reply=envelope({"executionStatus": "SUCCEEDED"}))
        data = client(t).execute_tool(
            "task-1", "step-1", "action-1", "route.recommend",
            {"walkDurationMin": 40, "avoidSteps": True},
        )
        call = t.calls[0]
        self.assertEqual(call["path"], "/internal/agent/v3/tools")
        self.assertEqual(call["headers"]["X-Agent-Context"], "context-token-1")
        self.assertEqual(call["body"], {
            "protocolVersion": "3.0",
            "taskId": "task-1",
            "actionId": "action-1",
            "input": {
                "tool": "route.recommend",
                "args": {"walkDurationMin": 40, "avoidSteps": True},
                "confirmationId": None,
            },
            "stepId": "step-1",
        })
        self.assertEqual(data, {"executionStatus": "SUCCEEDED"})

    def test_tool_execution_requires_context_before_network(self):
        t = RecordingTransport()
        with self.assertRaises(P2Error) as error:
            client(t, context_token=None).execute_tool(
                "task-1", "step-1", "action-1", "route.recommend", {}
            )
        self.assertIn("X-Agent-Context", str(error.exception))
        self.assertEqual(t.calls, [])

    def test_tool_execution_rejects_invalid_confirmation(self):
        t = RecordingTransport()
        with self.assertRaises(P2Error):
            client(t).execute_tool("task-1", "step-1", "action-1",
                                   "route.recommend", {}, confirmation_id="")
        self.assertEqual(t.calls, [])

    def test_missing_key_never_sends(self):
        t = RecordingTransport()
        with self.assertRaises(P2Error) as error:
            client(t, key=None).delegate("c", "t", "a", {})
        self.assertIn("A1_AGENT_KEY", str(error.exception))
        self.assertEqual(t.calls, [])

    def test_too_long_identifier_rejected_locally(self):
        t = RecordingTransport()
        with self.assertRaises(P2Error):
            client(t).delegate("c", "x" * 129, "a", {})
        self.assertEqual(t.calls, [])

    def test_bad_plan_version_rejected(self):
        t = RecordingTransport()
        for bad in (0, True, "2", 1.5):
            with self.assertRaises(P2Error):
                client(t).register_steps("task-1", "k", bad, [{"stepId": "s"}])
        self.assertEqual(t.calls, [])

    def test_error_envelope_is_reported_without_data(self):
        t = RecordingTransport(reply=json.dumps({"code": "FORBIDDEN", "message": "无权限", "data": {"secret": 1}}))
        with self.assertRaises(P2Error) as error:
            client(t).delegate("c", "t", "a", {})
        self.assertIn("FORBIDDEN", str(error.exception))
        self.assertNotIn("secret", str(error.exception))

    def test_transport_failure_becomes_fixed_message(self):
        t = RecordingTransport(raises=P2Error("P2 网关不可达或超时，未创建任何任务"))
        with self.assertRaises(P2Error) as error:
            client(t).delegate("c", "t", "a", {})
        self.assertIn("未创建任何任务", str(error.exception))

    def test_malformed_or_truncated_reply_rejected(self):
        for reply in ("", "not json", "[]", json.dumps({"code": "OK"}), "x" * (257 * 1024)):
            with self.assertRaises(P2Error):
                client(RecordingTransport(reply=reply)).delegate("c", "t", "a", {})

    def test_client_never_invents_ids(self):
        t = RecordingTransport(reply=envelope({}))
        data = client(t).delegate("c", "t", "a", {})
        self.assertEqual(data, {})  # 空就是空，不补 delegationId


if __name__ == "__main__":
    unittest.main()
