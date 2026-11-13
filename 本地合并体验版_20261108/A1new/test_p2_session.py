import unittest

from p2_public import P2PublicError
from p2_session import P2TaskSession


class Client:
    def __init__(self):
        self.submit_calls = []
        self.task = {"taskId": "task-1", "version": 4, "status": "RUNNING"}
        self.submit_error = None

    def submit_message(self, *args, **kwargs):
        self.submit_calls.append((args, kwargs))
        if self.submit_error:
            raise self.submit_error
        return {"conversationId": "conv-1", "taskId": "task-1", "taskVersion": 1,
                "taskStatus": "QUEUED"}

    def get_task(self, task_id):
        self.last_task_id = task_id
        return dict(self.task)

    def list_tasks(self, user_id, limit=20):
        self.list_call = (user_id, limit)
        return [{"taskId": "task-1", "conversationId": "conv-1"}]

    def cancel_task(self, task_id, version, key, reason):
        self.cancel_call = (task_id, version, key, reason)
        return {"taskId": task_id, "version": version + 1, "status": "CANCEL_REQUESTED"}

    def get_confirmation(self, confirmation_id):
        self.confirmation_id = confirmation_id
        return {"confirmationId": confirmation_id, "version": 2, "state": "PENDING"}

    def decide_confirmation(self, confirmation_id, decision, version, key):
        self.decision_call = (confirmation_id, decision, version, key)
        return {"confirmationId": confirmation_id, "version": version + 1, "state": decision}

    def upload_attachment(self, user_id, purpose, filename, content_type, content):
        self.upload_call = (user_id, purpose, filename, content_type, content)
        return {"attachmentId": "att-1", "state": "READY"}


class P2TaskSessionTests(unittest.TestCase):
    def test_acceptance_saves_ids_for_next_message(self):
        client = Client(); session = P2TaskSession(client, "u1")
        session.submit("杭州两天")
        session.submit("少走路")
        self.assertEqual(session.conversation_id, "conv-1")
        self.assertEqual(session.task_id, "task-1")
        self.assertEqual(client.submit_calls[1][1]["conversation_id"], "conv-1")

    def test_uncertain_retry_reuses_key_for_same_payload(self):
        client = Client(); session = P2TaskSession(client, "u1")
        client.submit_error = P2PublicError("结果不确定", uncertain=True)
        for _ in range(2):
            with self.assertRaises(P2PublicError):
                session.submit("同一条消息")
        first = client.submit_calls[0][0][2]
        second = client.submit_calls[1][0][2]
        self.assertEqual(first, second)

    def test_different_payload_gets_new_key(self):
        client = Client(); session = P2TaskSession(client, "u1")
        client.submit_error = P2PublicError("结果不确定", uncertain=True)
        with self.assertRaises(P2PublicError): session.submit("消息一")
        with self.assertRaises(P2PublicError): session.submit("消息二")
        self.assertNotEqual(client.submit_calls[0][0][2], client.submit_calls[1][0][2])

    def test_cancel_fetches_latest_version(self):
        client = Client(); session = P2TaskSession(client, "u1")
        session.task_id = "task-1"; session.task_version = 1
        result = session.cancel("不再需要")
        self.assertEqual(client.cancel_call[1], 4)
        self.assertEqual(result["status"], "CANCEL_REQUESTED")
        self.assertEqual(session.task_version, 5)

    def test_reset_does_not_call_cancel(self):
        client = Client(); session = P2TaskSession(client, "u1")
        session.conversation_id = "conv"; session.task_id = "task"
        session.reset_local_reference()
        self.assertIsNone(session.task_id)
        self.assertFalse(hasattr(client, "cancel_call"))

    def test_each_confirmation_decision_uses_a_new_key(self):
        client = Client(); session = P2TaskSession(client, "u1")
        self.assertEqual(session.get_confirmation("confirm-1")["version"], 2)
        session.decide_confirmation("confirm-1", "APPROVE", 2)
        first = client.decision_call[3]
        session.decide_confirmation("confirm-2", "REJECT", 1)
        self.assertNotEqual(first, client.decision_call[3])

    def test_upload_image_requires_ready_attachment(self):
        client = Client(); session = P2TaskSession(client, "u1")
        self.assertEqual(session.upload_image("fraud_analysis", "x.png", "image/png", b"x")["attachmentId"], "att-1")
        self.assertEqual(client.upload_call[0:2], ("u1", "fraud_analysis"))
        client.upload_attachment = lambda *args: {"attachmentId": "att-2", "state": "SCANNING"}
        with self.assertRaises(P2PublicError):
            session.upload_image("travel_reference", "x.png", "image/png", b"x")

    def test_restore_latest_uses_list_then_authoritative_snapshot(self):
        client = Client(); session = P2TaskSession(client, "u1")
        result = session.restore_latest()
        self.assertEqual(client.list_call, ("u1", 20))
        self.assertEqual(session.task_id, "task-1")
        self.assertEqual(session.conversation_id, "conv-1")
        self.assertEqual(session.task_version, 4)
        self.assertEqual(result["status"], "RUNNING")

    def test_restore_empty_history_does_not_invent_task(self):
        client = Client(); client.list_tasks = lambda *args, **kwargs: []
        session = P2TaskSession(client, "u1")
        self.assertIsNone(session.restore_latest())
        self.assertIsNone(session.task_id)


if __name__ == "__main__":
    unittest.main()
