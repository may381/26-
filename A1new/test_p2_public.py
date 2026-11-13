import json
import unittest

from p2_public import P2PublicClient, P2PublicError


def envelope(data=None, code="OK", message="成功"):
    return json.dumps({"code": code, "message": message, "data": data}, ensure_ascii=False)


class Transport:
    def __init__(self, result=None):
        self.calls = []
        self.result = result if result is not None else envelope({"taskId": "task-1"})

    def __call__(self, method, path, body, headers):
        self.calls.append((method, path, body, headers))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class P2PublicClientTests(unittest.TestCase):
    def test_submit_message_uses_complete_v3_body_and_key(self):
        transport = Transport()
        client = P2PublicClient(transport=transport, identity_headers={"X-User": "u1"})
        client.submit_message("u1", "杭州两天，少走路", "message-key-1")
        method, path, body, headers = transport.calls[0]
        self.assertEqual((method, path), ("POST", "/api/v3/agent/messages"))
        self.assertEqual(headers["Idempotency-Key"], "message-key-1")
        self.assertEqual(headers["X-User"], "u1")
        self.assertEqual(body["context"], {"businessRefs": []})
        self.assertIsNone(body["continueTaskId"])

    def test_question_answer_requires_continue_task(self):
        client = P2PublicClient(transport=Transport())
        response_to = {"ownerTaskId": "child-1", "inputRequestId": "question-1", "version": 2}
        with self.assertRaises(P2PublicError):
            client.submit_message("u1", "长沙", "key-1", response_to=response_to)

    def test_query_cancel_and_confirmation_use_separate_versions(self):
        transport = Transport()
        client = P2PublicClient(transport=transport)
        client.get_task("task/1")
        client.cancel_task("task-1", 7, "cancel-key")
        client.decide_confirmation("confirm-1", "APPROVE", 3, "confirm-key")
        self.assertEqual(transport.calls[0][1], "/api/v3/agent/tasks/task%2F1")
        self.assertEqual(transport.calls[1][2]["expectedVersion"], 7)
        self.assertEqual(transport.calls[2][2]["expectedVersion"], 3)

    def test_upload_attachment_uses_multipart_and_no_idempotency_key(self):
        transport = Transport(envelope({"attachmentId": "att-1", "state": "READY"}))
        client = P2PublicClient(transport=transport)
        result = client.upload_attachment("u1", "fraud_analysis", "截图.png", "image/png", b"PNG")
        method, path, body, headers = transport.calls[0]
        self.assertEqual(method, "POST")
        self.assertIn("userId=u1", path)
        self.assertIn("purpose=fraud_analysis", path)
        self.assertIn(b'name="file"', body)
        self.assertIn(b"PNG", body)
        self.assertTrue(headers["Content-Type"].startswith("multipart/form-data; boundary="))
        self.assertNotIn("Idempotency-Key", headers)
        self.assertEqual(result["attachmentId"], "att-1")

    def test_delete_attachment_scopes_request_to_user(self):
        transport = Transport(envelope(None))
        P2PublicClient(transport=transport).delete_attachment("u1", "att/1")
        self.assertEqual(transport.calls[0][0], "DELETE")
        self.assertEqual(transport.calls[0][1], "/api/v3/agent/attachments/att%2F1?userId=u1")

    def test_invalid_write_is_rejected_before_transport(self):
        transport = Transport()
        client = P2PublicClient(transport=transport)
        for call in (
            lambda: client.submit_message("u1", "", "key"),
            lambda: client.cancel_task("task", 0, "key"),
            lambda: client.decide_confirmation("c1", "YES", 1, "key"),
        ):
            with self.assertRaises(P2PublicError):
                call()
        self.assertEqual(transport.calls, [])

    def test_error_envelope_does_not_return_data(self):
        client = P2PublicClient(transport=Transport(envelope({"secret": 1}, "FORBIDDEN", "无权限")))
        with self.assertRaises(P2PublicError) as error:
            client.get_task("task-1")
        self.assertNotIn("secret", str(error.exception))


if __name__ == "__main__":
    unittest.main()
