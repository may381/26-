"""A1new → P2 v3 公共任务接口客户端。"""
import json
import socket
import secrets
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


class P2PublicError(Exception):
    def __init__(self, message, uncertain=False):
        super().__init__(message)
        self.uncertain = uncertain


def _text(value, name, limit=128, optional=False):
    if optional and value is None:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise P2PublicError(f"{name} 无效")
    return value.strip()


def _version(value, name="expectedVersion"):
    if type(value) is not int or value < 1:
        raise P2PublicError(f"{name} 必须是大于等于1的整数")
    return value


class P2PublicClient:
    def __init__(self, base="http://127.0.0.1:8080", timeout=30, transport=None,
                 identity_headers=None):
        self.base = base.rstrip("/")
        self.timeout = timeout
        self.transport = transport or self._request
        self.identity_headers = dict(identity_headers or {})

    def submit_message(self, user_id, text, idempotency_key, conversation_id=None,
                       continue_task_id=None, response_to=None, attachment_ids=None,
                       related_task_id=None):
        user_id = _text(user_id, "userId")
        text = text if isinstance(text, str) else ""
        attachments = [] if attachment_ids is None else attachment_ids
        if len(text) > 2000 or (not text.strip() and not attachments):
            raise P2PublicError("文字与附件至少提供一项，文字最多2000字")
        if (not isinstance(attachments, list) or len(attachments) > 4
                or not all(isinstance(item, str) and 0 < len(item) <= 128 for item in attachments)):
            raise P2PublicError("attachmentIds 无效")
        if response_to is not None:
            if not isinstance(response_to, dict):
                raise P2PublicError("responseTo 无效")
            required = {"ownerTaskId", "inputRequestId", "version"}
            if not required.issubset(response_to) or type(response_to["version"]) is not int or response_to["version"] < 1:
                raise P2PublicError("responseTo 缺少问题归属、ID或有效版本")
            if continue_task_id is None:
                raise P2PublicError("回答问题必须提供 continueTaskId")
        body = {
            "protocolVersion": "3.0",
            "userId": user_id,
            "conversationId": _text(conversation_id, "conversationId", optional=True),
            "continueTaskId": _text(continue_task_id, "continueTaskId", optional=True),
            "input": {"text": text, "attachmentIds": attachments, "responseTo": response_to},
            "context": {"businessRefs": []},
            "relatedTaskId": _text(related_task_id, "relatedTaskId", optional=True),
        }
        return self._call("POST", "/api/v3/agent/messages", body, idempotency_key)

    def upload_attachment(self, user_id, purpose, filename, content_type, content):
        user_id = _text(user_id, "userId")
        if purpose not in ("fraud_analysis", "travel_reference"):
            raise P2PublicError("purpose 无效")
        filename = _text(filename, "filename", 255)
        if content_type not in ("image/jpeg", "image/png"):
            raise P2PublicError("仅支持JPEG或PNG图片")
        if not isinstance(content, bytes) or not 1 <= len(content) <= 10 * 1024 * 1024:
            raise P2PublicError("图片大小必须在1字节至10MiB之间")
        boundary = "----A1P2" + secrets.token_hex(16)
        disposition = ('Content-Disposition: form-data; name="file"; filename="%s"\r\n'
                       % filename.replace('"', ""))
        body = (("--" + boundary + "\r\n" + disposition
                 + "Content-Type: " + content_type + "\r\n\r\n").encode("utf-8")
                + content + ("\r\n--" + boundary + "--\r\n").encode("ascii"))
        query = urlencode({"userId": user_id, "purpose": purpose})
        return self._call("POST", "/api/v3/agent/attachments?" + query, body,
                          extra_headers={"Content-Type": "multipart/form-data; boundary=" + boundary},
                          require_idempotency=False)

    def delete_attachment(self, user_id, attachment_id):
        query = urlencode({"userId": _text(user_id, "userId")})
        path = "/api/v3/agent/attachments/" + quote(_text(attachment_id, "attachmentId"), safe="")
        return self._call("DELETE", path + "?" + query)

    def get_task(self, task_id):
        return self._call("GET", "/api/v3/agent/tasks/" + quote(_text(task_id, "taskId"), safe=""))

    def list_tasks(self, user_id, limit=20):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise P2PublicError("limit 必须在1至100之间")
        query = urlencode({"userId": _text(user_id, "userId"), "limit": limit})
        return self._call("GET", "/api/v3/agent/tasks?" + query)

    def cancel_task(self, task_id, expected_version, idempotency_key, reason="用户取消"):
        body = {"expectedVersion": _version(expected_version),
                "reason": _text(reason, "reason", 500)}
        return self._call("POST", "/api/v3/agent/tasks/" + quote(_text(task_id, "taskId"), safe="") + "/cancel",
                          body, idempotency_key)

    def get_confirmation(self, confirmation_id):
        path = "/api/v3/agent/confirmations/" + quote(_text(confirmation_id, "confirmationId"), safe="")
        return self._call("GET", path)

    def decide_confirmation(self, confirmation_id, decision, expected_version,
                            idempotency_key):
        if decision not in ("APPROVE", "REJECT", "CANCEL"):
            raise P2PublicError("decision 无效")
        body = {"protocolVersion": "3.0", "decision": decision,
                "expectedVersion": _version(expected_version)}
        path = "/api/v3/agent/confirmations/" + quote(_text(confirmation_id, "confirmationId"), safe="") + "/decision"
        return self._call("POST", path, body, idempotency_key)

    def _call(self, method, path, body=None, idempotency_key=None,
              extra_headers=None, require_idempotency=True):
        headers = dict(self.identity_headers)
        headers.update(extra_headers or {})
        if method == "POST" and require_idempotency:
            headers["Idempotency-Key"] = _text(idempotency_key, "Idempotency-Key")
        raw = self.transport(method, path, body, headers)
        if not isinstance(raw, str) or len(raw) > 512 * 1024:
            raise P2PublicError("P2 返回内容无效或过大")
        try:
            envelope = json.loads(raw)
        except ValueError:
            raise P2PublicError("P2 返回不是有效JSON") from None
        if not isinstance(envelope, dict) or "code" not in envelope or "data" not in envelope:
            raise P2PublicError("P2 返回缺少code/data")
        if envelope["code"] != "OK":
            message = envelope.get("message")
            detail = message if isinstance(message, str) and len(message) <= 200 else "未提供原因"
            raise P2PublicError(f"P2拒绝请求：{envelope['code']}（{detail}）")
        return envelope["data"]

    def _request(self, method, path, body, headers):
        data = body if isinstance(body, bytes) else (None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8"))
        request = Request(self.base + path, data=data, method=method,
                          headers={"Content-Type": "application/json", **headers})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read(512 * 1024 + 1)
            if len(raw) > 512 * 1024:
                raise P2PublicError("P2 返回内容过大")
            return raw.decode("utf-8")
        except HTTPError as error:
            raise P2PublicError(f"P2返回HTTP {error.code}") from None
        except (URLError, socket.timeout, TimeoutError, OSError):
            uncertain = method == "POST"
            message = "P2写请求结果未确认，请使用原幂等键核查或重试" if uncertain else "P2任务查询不可达"
            raise P2PublicError(message, uncertain=uncertain) from None

