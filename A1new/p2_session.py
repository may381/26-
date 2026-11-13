"""A1new 单个浏览器会话对应的 P2 v3 任务状态。"""
import hashlib
import json
import uuid

from p2_public import P2PublicError


class P2TaskSession:
    def __init__(self, client, user_id):
        self.client = client
        self.user_id = user_id
        self.conversation_id = None
        self.task_id = None
        self.task_version = None
        self._pending_digest = None
        self._pending_key = None

    @staticmethod
    def _digest(payload):
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def submit(self, text, continue_task_id=None, response_to=None,
               attachment_ids=None, related_task_id=None):
        payload = {
            "text": text,
            "conversationId": self.conversation_id,
            "continueTaskId": continue_task_id,
            "responseTo": response_to,
            "attachmentIds": attachment_ids or [],
            "relatedTaskId": related_task_id,
        }
        digest = self._digest(payload)
        if digest != self._pending_digest:
            self._pending_digest = digest
            self._pending_key = "message-" + str(uuid.uuid4())
        try:
            accepted = self.client.submit_message(
                self.user_id, text, self._pending_key,
                conversation_id=self.conversation_id,
                continue_task_id=continue_task_id,
                response_to=response_to,
                attachment_ids=attachment_ids,
                related_task_id=related_task_id,
            )
        except P2PublicError as error:
            if not error.uncertain:
                self._pending_digest = None
                self._pending_key = None
            raise
        if not isinstance(accepted, dict):
            raise P2PublicError("P2受理结果缺少任务信息")
        conversation = accepted.get("conversationId")
        task = accepted.get("taskId")
        version = accepted.get("taskVersion")
        if (not isinstance(conversation, str) or not conversation
                or not isinstance(task, str) or not task
                or type(version) is not int or version < 1):
            raise P2PublicError("P2受理结果缺少有效conversationId、taskId或taskVersion")
        self.conversation_id = conversation
        self.task_id = task
        self.task_version = version
        self._pending_digest = None
        self._pending_key = None
        return accepted

    def status(self):
        if not self.task_id:
            raise P2PublicError("当前会话没有可查询的P2任务")
        task = self.client.get_task(self.task_id)
        if not isinstance(task, dict):
            raise P2PublicError("P2任务快照无效")
        version = task.get("version", task.get("taskVersion"))
        if type(version) is int and version >= 1:
            self.task_version = version
        return task

    def restore_latest(self):
        """从P2权威任务列表恢复最近一个根任务；不根据本地缓存猜状态。"""
        rows = self.client.list_tasks(self.user_id, limit=20)
        if not isinstance(rows, list):
            raise P2PublicError("P2任务列表无效")
        if not rows:
            return None
        task = rows[0]
        if not isinstance(task, dict):
            raise P2PublicError("P2最近任务摘要无效")
        task_id = task.get("taskId", task.get("id"))
        if not isinstance(task_id, str) or not task_id:
            raise P2PublicError("P2最近任务缺少taskId")
        snapshot = self.client.get_task(task_id)
        if not isinstance(snapshot, dict):
            raise P2PublicError("P2最近任务快照无效")
        conversation_id = snapshot.get("conversationId", task.get("conversationId"))
        version = snapshot.get("version", snapshot.get("taskVersion"))
        if (not isinstance(conversation_id, str) or not conversation_id
                or type(version) is not int or version < 1):
            raise P2PublicError("P2最近任务缺少有效会话或版本")
        self.conversation_id = conversation_id
        self.task_id = task_id
        self.task_version = version
        self._pending_digest = None
        self._pending_key = None
        return snapshot

    def cancel(self, reason="用户取消"):
        task = self.status()
        version = task.get("version", task.get("taskVersion"))
        if type(version) is not int or version < 1:
            raise P2PublicError("P2任务快照缺少最新版本，未取消")
        key = "cancel-" + str(uuid.uuid4())
        result = self.client.cancel_task(self.task_id, version, key, reason)
        if isinstance(result, dict):
            new_version = result.get("version", result.get("taskVersion"))
            if type(new_version) is int and new_version >= version:
                self.task_version = new_version
        return result

    def get_confirmation(self, confirmation_id):
        return self.client.get_confirmation(confirmation_id)

    def decide_confirmation(self, confirmation_id, decision, expected_version):
        key = "confirmation-" + str(uuid.uuid4())
        return self.client.decide_confirmation(confirmation_id, decision, expected_version, key)

    def upload_image(self, purpose, filename, content_type, content):
        result = self.client.upload_attachment(self.user_id, purpose, filename, content_type, content)
        if not isinstance(result, dict):
            raise P2PublicError("P2附件上传结果无效")
        attachment_id = result.get("attachmentId")
        state = result.get("state")
        if not isinstance(attachment_id, str) or not attachment_id:
            raise P2PublicError("P2附件上传结果缺少attachmentId")
        if state != "READY":
            raise P2PublicError("P2附件尚未通过检查，不能提交任务")
        return result

    def reset_local_reference(self):
        self.conversation_id = None
        self.task_id = None
        self.task_version = None
        self._pending_digest = None
        self._pending_key = None

