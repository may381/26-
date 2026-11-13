"""A1 → P2 的出站客户端（v3 内部接口）。

字段依据 `后端资料/P2统一接口协议_v3.0_开发包/agent-v3-r3/control.schema.json`：
    DelegationRequest            required: protocolVersion, conversationId, taskId, actionId, input
    StepRegisterRequest          required: protocolVersion, taskId, requestKey, planVersion, steps
    ActionPrepareRequest         required: protocolVersion, taskId, stepId, input
    ConfirmationPrepareRequest   required: protocolVersion, taskId, actionId
    ToolExecutionRequest         required: protocolVersion, taskId, actionId, input, stepId

设计原则（和 A1 其它部分一致）
1. **只发，不猜**：响应必须是有 `code/message/data` 的信封；缺字段就报错，
   绝不自造 delegationId / stepId / actionId / confirmationId。
2. **失败即失败**：连不上、超时、HTTP 错、信封不合法，一律抛 P2Error 固定文案；
   不重试（重试会造重复副作用），由调用方决定是否恢复。
3. **本地先校验**：协议版本、必填、长度上限在发请求前就拦住，不浪费一次网络。
4. **没有 P2 也不装**：`available()` 只做配置检查和 TCP 探测，不表示业务可用。

未接通时的行为：任何写操作前需要 A1_AGENT_KEY；没有就抛错，不会发半个请求。
"""
import json
import os
import socket
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PROTOCOL_VERSION = "3.0"
DEFAULT_BASE = "http://127.0.0.1:8080"

PATHS = {
    "delegation": "/internal/agent/v3/delegations",
    "steps": "/internal/agent/v3/tasks/{taskId}/steps",
    "actions": "/internal/agent/v3/actions",
    "confirmations": "/internal/agent/v3/confirmations",
    "tools": "/internal/agent/v3/tools",
}


class P2Error(Exception):
    """固定的、可以直接给用户/日志看的失败原因；不携带上游原始报文。"""


def _need_str(value, name, limit=128):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise P2Error("%s 无效：需为 1–%d 字符的非空字符串" % (name, limit))
    return value.strip()


def _need_obj(value, name):
    if not isinstance(value, dict):
        raise P2Error("%s 无效：需为对象" % name)
    return value


class P2Client:
    def __init__(self, transport=None, base=None, key=None, timeout=30, trace_id=None,
                 context_token=None):
        self.base = (base or os.environ.get("A1_P2_URL") or DEFAULT_BASE).rstrip("/")
        self.key = key if key is not None else os.environ.get("A1_AGENT_KEY")
        self.timeout = timeout
        self.trace_id = trace_id
        self.context_token = context_token if context_token is not None else os.environ.get("A1_AGENT_CONTEXT")
        self.transport = transport or self._request

    # ---- 配置与探活 ----

    def configured(self):
        return bool(self.key)

    def available(self):
        """只证明端口可达，不证明 P2 会接受请求。"""
        try:
            with socket.create_connection(
                (self.base.split("://")[-1].split(":")[0],
                 int(self.base.rsplit(":", 1)[-1] or 80)), timeout=1):
                return True
        except (OSError, ValueError):
            return False

    # ---- 出站动作 ----

    def delegate(self, conversation_id, task_id, action_id, payload, idempotency_key=None):
        body = {
            "protocolVersion": PROTOCOL_VERSION,
            "conversationId": _need_str(conversation_id, "conversationId"),
            "taskId": _need_str(task_id, "taskId"),
            "actionId": _need_str(action_id, "actionId"),
            "input": _need_obj(payload, "input"),
        }
        return self._send("delegation", body, idempotency_key)

    def register_steps(self, task_id, request_key, plan_version, steps, idempotency_key=None):
        if not isinstance(plan_version, int) or isinstance(plan_version, bool) or plan_version < 1:
            raise P2Error("planVersion 无效：需为 ≥1 的整数")
        if not isinstance(steps, list) or not steps or not all(isinstance(s, dict) for s in steps):
            raise P2Error("steps 无效：需为非空对象数组")
        body = {
            "protocolVersion": PROTOCOL_VERSION,
            "taskId": _need_str(task_id, "taskId"),
            "requestKey": _need_str(request_key, "requestKey"),
            "planVersion": plan_version,
            "steps": steps,
        }
        return self._send("steps", body, idempotency_key, task_id=body["taskId"])

    def prepare_action(self, task_id, step_id, payload, idempotency_key):
        # 动作准备必须带 Idempotency-Key：它可能引出真实副作用。
        _need_str(idempotency_key, "Idempotency-Key")
        body = {
            "protocolVersion": PROTOCOL_VERSION,
            "taskId": _need_str(task_id, "taskId"),
            "stepId": _need_str(step_id, "stepId"),
            "input": _need_obj(payload, "input"),
        }
        return self._send("actions", body, idempotency_key)

    def prepare_confirmation(self, task_id, action_id, idempotency_key=None):
        body = {
            "protocolVersion": PROTOCOL_VERSION,
            "taskId": _need_str(task_id, "taskId"),
            "actionId": _need_str(action_id, "actionId"),
        }
        return self._send("confirmations", body, idempotency_key)

    def execute_tool(self, task_id, step_id, action_id, tool, args,
                     confirmation_id=None):
        """执行 P2 已准备并授权的动作，不在客户端重新解释或修改参数。"""
        _need_str(self.context_token, "X-Agent-Context", 4096)
        if confirmation_id is not None:
            confirmation_id = _need_str(confirmation_id, "confirmationId")
        body = {
            "protocolVersion": PROTOCOL_VERSION,
            "taskId": _need_str(task_id, "taskId"),
            "actionId": _need_str(action_id, "actionId"),
            "input": {
                "tool": _need_str(tool, "tool"),
                "args": _need_obj(args, "args"),
                "confirmationId": confirmation_id,
            },
            "stepId": _need_str(step_id, "stepId"),
        }
        return self._send("tools", body, require_context=True)

    # ---- 传输与错误归一 ----

    def _send(self, kind, body, idempotency_key=None, task_id=None, require_context=False):
        if not self.configured():
            raise P2Error("未配置 A1_AGENT_KEY，未向 P2 发送任何请求")
        path = PATHS[kind].format(taskId=task_id or "")
        headers = {"X-Agent-Key": self.key}
        if require_context and not self.context_token:
            raise P2Error("未配置 X-Agent-Context，未向 P2 执行工具")
        if isinstance(self.context_token, str) and self.context_token.strip():
            headers["X-Agent-Context"] = self.context_token.strip()
        if isinstance(idempotency_key, str) and idempotency_key.strip():
            headers["Idempotency-Key"] = idempotency_key.strip()
        if isinstance(self.trace_id, str) and self.trace_id.strip():
            headers["X-Trace-Id"] = self.trace_id.strip()
        raw = self.transport("POST", path, body, headers)
        return self._unwrap(raw)

    def _request(self, method, path, body, headers):
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = Request(self.base + path, data=data, method=method,
                          headers={"Content-Type": "application/json", **headers})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return response.read(256 * 1024 + 1).decode("utf-8")
        except HTTPError as error:
            raise P2Error("P2 网关返回 HTTP %s，未假定业务成功" % error.code) from None
        except (URLError, socket.timeout, TimeoutError, OSError):
            raise P2Error("P2 网关不可达或超时，未创建任何任务") from None

    @staticmethod
    def _unwrap(raw):
        if not isinstance(raw, str) or len(raw) > 256 * 1024:
            raise P2Error("P2 返回内容无效或被截断，未采用")
        try:
            envelope = json.loads(raw)
        except ValueError:
            raise P2Error("P2 返回不是有效 JSON，未采用") from None
        if not isinstance(envelope, dict) or envelope.get("code") is None or "data" not in envelope:
            raise P2Error("P2 返回缺少 code/data，未采用")
        if envelope["code"] != "OK":
            message = envelope.get("message")
            reason = message if isinstance(message, str) and 0 < len(message) <= 200 else "未提供原因"
            raise P2Error("P2 拒绝：%s（%s）" % (envelope["code"], reason))
        return envelope["data"]
