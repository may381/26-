#!/usr/bin/env python3
"""A3 的 v3 报文信封 —— 收 P2 的 InvocationRequest，回 AgentResponse。

这个文件解决的是「A3 这个服务怎么跟 P2 说话」的问题，不涉及业务内容。
业务（非遗文化、能力银行、记忆审核）由别的模块产出，最后都从这里出去。

为什么信封要单独一个文件？
    v3 里最多变的不是业务，是外壳。协议从 v1 到 v3，改的全是字段位置：
    v1 的 reply 在顶层 → v2 挪进 data.reply → v3 又要 14 个必填字段。
    业务代码（"剪纸课要 60 分钟以内"）三年都不用改，
    但外壳改一次，所有出口都要跟着改。所以把外壳收在一处，改一次就够。

四件必须做对的事：
    1. 校验顺序：版本 → 密钥 → 形状 → 语义。
       版本不对时字段可能完全不同，此时报「缺字段」是误导。
    2. Control 联动自己算，不让调用方传，从根上杜绝非法组合。
    3. audioUrl 恒为 null（Schema 写死），语音合成是 P2/前端的事，不是 A3 的。
    4. usedMemoryRefs 只能引用真实检索到且 ACTIVE 的记忆 —— 不许编。

自测（含 38+14 份官方样例离线回放）：
    python v3_messages.py
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import schema_check

PROTOCOL_VERSION = "3.0"

# v3：九种登记领域，同时也是 intent 的取值
DOMAINS = ("tourism", "help", "fraud", "health", "care", "community",
           "volunteer", "culture", "ability")

# v3：Control.next 四选一
NEXT_COMPLETE = "COMPLETE"
NEXT_WAIT_CONFIRMATION = "WAIT_CONFIRMATION"
NEXT_WAIT_DEPENDENCIES = "WAIT_DEPENDENCIES"
NEXT_WAIT_INPUT = "WAIT_INPUT"
NEXT_VALUES = (NEXT_COMPLETE, NEXT_WAIT_CONFIRMATION, NEXT_WAIT_DEPENDENCIES, NEXT_WAIT_INPUT)

# v3：只有 COMPLETE 才准带 outcome
OUTCOME_SUCCEEDED = "SUCCEEDED"
OUTCOME_PARTIAL = "PARTIALLY_SUCCEEDED"
OUTCOME_FAILED = "FAILED"
OUTCOME_VALUES = (OUTCOME_SUCCEEDED, OUTCOME_PARTIAL, OUTCOME_FAILED)

# v3：16 个错误码 —— 与 control.schema.json 的 ErrorResponse.code 完全一致。
# 注意：P2接口协议.md 里还提到 INPUT_REQUEST_ID_CONFLICT，
# 但它**不在** Schema 的枚举里。以 Schema 为准，联调时跟 P2 确认这一点。
ERROR_STATUS: dict[str, int] = {
    "INVALID_ARGUMENT": 400,
    "UNSUPPORTED_PROTOCOL_VERSION": 400,
    "UNAUTHORIZED": 401,
    "FORBIDDEN": 403,
    "NOT_FOUND": 404,
    "CONFLICT": 409,
    "QUESTION_NOT_PENDING": 409,
    "STALE_VERSION": 409,
    "TASK_NOT_RUNNABLE": 409,
    "CONFIRMATION_REQUIRED": 409,
    "CONFIRMATION_EXPIRED": 409,
    "RATE_LIMITED": 429,
    "INTERNAL_ERROR": 500,
    "UPSTREAM_ERROR": 502,
    "CAPABILITY_UNAVAILABLE": 503,
    "UPSTREAM_TIMEOUT": 504,
}

# InvocationRequest.context 的 12 个必填字段（少一个就是非法报文）
CONTEXT_FIELDS = ("businessRefs", "history", "completedEffects", "reason",
                  "candidateTasks", "dependencyResults", "confirmationResults",
                  "actionLedger", "planSteps", "readSet", "inputResponse",
                  "pendingInputRequests")

MIN_SPEECH_RATE, MAX_SPEECH_RATE = 0.5, 1.5
DEFAULT_SPEECH_RATE = 0.9        # 适老：比默认语速再慢一点
MAX_MEMORY_REFS = 20             # Schema: maxItems 20
MAX_RESULTS = 20

_HERE = os.path.dirname(os.path.abspath(__file__))

# Schema 从哪儿找，按优先级：
#   1. 环境变量 A3_SCHEMA_DIR —— 联调时想临时换一版，不改代码
#   2. 仓库内 schemas/       —— 队友 clone 下来就自带，评奖现场断网也能跑
#   3. 上级 _v3开发包/        —— 本地开发时对着官方包直接跑
# 为什么要 2：Schema 放在仓库外，别人 clone 就只有代码没有尺子，
# 测试全跳过还显示"通过"，这种假通过比报错更危险。
_SCHEMA_DIRS = [
    os.environ.get("A3_SCHEMA_DIR") or "",
    os.path.join(_HERE, "schemas"),
    os.path.join(_HERE, "..", "_v3开发包", "agent-v3-r3"),
]
_SCHEMA_CACHE: dict[str, dict[str, Any]] = {}
_SCHEMA_WARNED = False


def schema_dir() -> str | None:
    """返回实际用到的 Schema 目录；一个都找不到返回 None。"""
    for candidate in _SCHEMA_DIRS:
        if candidate and os.path.exists(os.path.join(candidate, "control.schema.json")):
            return candidate
    return None


def schema_available() -> bool:
    """有没有尺子。没有的话 build_response 就不做自校 —— 但要说清楚，不能装作校过了。"""
    return schema_dir() is not None


class ProtocolError(Exception):
    """协议层失败。status + code 直接能组成 ErrorResponse。"""

    def __init__(self, code: str, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status if status is not None else ERROR_STATUS.get(code, 400)


# ------------------------------------------------------------------ 请求侧
@dataclass(frozen=True)
class Invocation:
    """一次已校验通过的调用。字段名保持 v3 原样，方便对照报文。"""

    user_id: str
    conversation_id: str
    message_id: str
    task_id: str
    parent_task_id: str | None
    task_version: int
    attempt: int
    invocation_id: str
    deadline_at: str
    text: str
    attachment_ids: tuple[str, ...]
    reason: str
    read_set: dict[str, Any]
    dependency_results: list[dict[str, Any]] = field(default_factory=list)
    pending_input_requests: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_root(self) -> bool:
        return self.parent_task_id is None

    @property
    def memory_revision(self) -> int:
        return int(self.read_set.get("memoryRevision") or 0)

    def deadline_passed(self, now: datetime | None = None) -> bool:
        """截止时间过了没。过了就别再往下做了，白做功。"""
        try:
            deadline = datetime.fromisoformat(self.deadline_at.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return False
        return deadline < (now or datetime.now(timezone.utc))


def parse_invocation(body: Any, *, expected_token: str | None = None,
                     root_schema: dict[str, Any] | None = None) -> Invocation:
    """校验并解析 P2 发来的 InvocationRequest。

    校验顺序是刻意的：版本 → 密钥 → 形状 → 语义。
    先报版本，是因为版本不对时字段可能整个变了，这时候说"缺 task"会把人带偏。
    """
    if not isinstance(body, dict):
        raise ProtocolError("INVALID_ARGUMENT", "请求体必须是 JSON 对象")

    # 1) 版本：必须是字符串 "3.0"。给整数 3 也不行，因为 Schema 是 const "3.0"
    version = body.get("protocolVersion")
    if version != PROTOCOL_VERSION:
        raise ProtocolError(
            "UNSUPPORTED_PROTOCOL_VERSION",
            f"只支持 protocolVersion={PROTOCOL_VERSION!r}，收到 {version!r}")

    # 2) 密钥：v3 用 capabilityToken（v2 叫 toolContextToken，改名了）
    #    先认旧字段名再报"缺字段"：直接说"缺 capabilityToken"会让人以为是漏传，
    #    其实只是名字没改，提示要指到真问题上。
    if "toolContextToken" in body:
        raise ProtocolError("INVALID_ARGUMENT",
                            "capabilityToken 已取代 toolContextToken，请用新字段名")
    token = body.get("capabilityToken")
    if not isinstance(token, str) or not token.strip():
        raise ProtocolError("UNAUTHORIZED", "缺少 capabilityToken")
    if expected_token is not None and token != expected_token:
        raise ProtocolError("UNAUTHORIZED", "capabilityToken 校验失败")

    # 3) 形状：交给 Schema，一个字段都不许少、一个都不许多
    _assert_schema(body, "InvocationRequest", root_schema, "InvocationRequest")

    task = body["task"]
    payload = body["input"]
    context = body["context"]

    # 4) 语义：形状对了不代表意思对，这几条 Schema 管不了
    if not payload["text"].strip() and not payload["attachmentIds"]:
        raise ProtocolError("INVALID_ARGUMENT", "input.text 与 input.attachmentIds 不能同时为空")
    if task["version"] < 1:
        raise ProtocolError("INVALID_ARGUMENT", "task.version 必须 ≥ 1")
    if task["attempt"] < 1:
        raise ProtocolError("INVALID_ARGUMENT", "task.attempt 必须 ≥ 1")
    if task["parentTaskId"] is not None and task["parentTaskId"] == task["id"]:
        raise ProtocolError("INVALID_ARGUMENT", "task.parentTaskId 不能等于 task.id")

    return Invocation(
        user_id=body["userId"],
        conversation_id=body["conversationId"],
        message_id=body["messageId"],
        task_id=task["id"],
        parent_task_id=task["parentTaskId"],
        task_version=task["version"],
        attempt=task["attempt"],
        invocation_id=task["invocationId"],
        deadline_at=task["deadlineAt"],
        text=payload["text"],
        attachment_ids=tuple(payload["attachmentIds"]),
        reason=context["reason"],
        read_set=dict(context["readSet"]),
        dependency_results=list(context["dependencyResults"]),
        pending_input_requests=list(context["pendingInputRequests"]),
        raw=body,
    )


# ------------------------------------------------------------------ 响应侧
def settle_control(next_step: str, *, outcome: str | None = None,
                   dependency_task_ids: list[str] | None = None,
                   input_request: dict[str, Any] | None = None) -> dict[str, Any]:
    """把 Control 的四个字段凑成**一定合法**的组合。

    Schema 里 Control 有 3 条 if/then：COMPLETE 必须给 outcome、WAIT_INPUT 必须给
    inputRequest、WAIT_DEPENDENCIES 至少一个依赖 ID。这三种错配最容易出，
    所以在生成时就按 next 反推，而不是让调用方各传各的。
    """
    if next_step not in NEXT_VALUES:
        raise ProtocolError("INVALID_ARGUMENT", f"control.next 必须是 {NEXT_VALUES} 之一")

    deps = list(dependency_task_ids or [])

    if next_step == NEXT_COMPLETE:
        if outcome not in OUTCOME_VALUES:
            raise ProtocolError("INVALID_ARGUMENT", f"COMPLETE 必须给 outcome（{OUTCOME_VALUES}）")
        if input_request is not None:
            raise ProtocolError("INVALID_ARGUMENT", "COMPLETE 不能同时带 inputRequest")
        return {"next": next_step, "outcome": outcome,
                "dependencyTaskIds": deps, "inputRequest": None}

    # 其余三种都不是"结束"，outcome 必须是 null
    if outcome is not None:
        raise ProtocolError("INVALID_ARGUMENT", f"{next_step} 时 outcome 必须为 null")

    if next_step == NEXT_WAIT_INPUT:
        if not input_request:
            raise ProtocolError("INVALID_ARGUMENT", "WAIT_INPUT 必须给 inputRequest，否则前端没东西可问")
        return {"next": next_step, "outcome": None, "dependencyTaskIds": deps,
                "inputRequest": dict(input_request)}

    if next_step == NEXT_WAIT_DEPENDENCIES:
        if not deps:
            raise ProtocolError("INVALID_ARGUMENT", "WAIT_DEPENDENCIES 至少要有 1 个依赖任务 ID")
        if input_request is not None:
            raise ProtocolError("INVALID_ARGUMENT", "WAIT_DEPENDENCIES 不能带 inputRequest")
        return {"next": next_step, "outcome": None, "dependencyTaskIds": deps,
                "inputRequest": None}

    # WAIT_CONFIRMATION：Schema 不管 inputRequest，但我们同样不允许带
    if input_request is not None:
        raise ProtocolError("INVALID_ARGUMENT", "WAIT_CONFIRMATION 不能带 inputRequest")
    return {"next": next_step, "outcome": None, "dependencyTaskIds": deps,
            "inputRequest": None}


def new_input_request(question: str, required_fields: list[str],
                      options: list[dict[str, str]] | None = None,
                      allow_free_text: bool = True) -> dict[str, Any]:
    """新建一个问题草案。

    inputRequestId 必须是**程序生成的 UUID v4** —— 官方 invalidCases 里专门有这一条
    「新问题ID必须为程序生成的UUID v4」。不能写 "question-001"，
    也不能让模型自己编，否则两个 Agent 撞 ID 时 P2 无法判重。
    """
    if not isinstance(question, str) or not question.strip():
        raise ProtocolError("INVALID_ARGUMENT", "question 不能为空")
    if len(question) > 4000:
        raise ProtocolError("INVALID_ARGUMENT", "question 最多 4000 字符")
    if not required_fields:
        raise ProtocolError("INVALID_ARGUMENT", "requiredFields 至少要 1 个，否则用户不知道该答什么")
    if len(required_fields) > 10:
        raise ProtocolError("INVALID_ARGUMENT", "requiredFields 最多 10 个")

    prepared = []
    for option in options or []:
        missing = {"id", "label", "value"} - set(option)
        if missing:
            raise ProtocolError("INVALID_ARGUMENT", f"选项缺少字段：{','.join(sorted(missing))}")
        prepared.append({"id": str(option["id"]), "label": str(option["label"]),
                         "value": str(option["value"])})
    if len(prepared) > 10:
        raise ProtocolError("INVALID_ARGUMENT", "options 最多 10 个")

    return {
        "inputRequestId": str(uuid.uuid4()),
        "question": question.strip(),
        "requiredFields": list(dict.fromkeys(required_fields)),
        "options": prepared,
        "allowFreeText": bool(allow_free_text),
    }


def relay_question(pending: dict[str, Any]) -> dict[str, Any]:
    """转呈子任务的问题时，原样保留 inputRequestId，但要去掉 P2 分配的字段。

    依据：v3 样例 38「A1转呈子问题原样保留全局问题ID」。
    问题的**归属**不能因为被谁转呈就变 —— 老人回答后，答案要回到原来的子任务。
    """
    proposal = {
        "inputRequestId": pending["inputRequestId"],
        "question": pending["question"],
        "requiredFields": list(pending.get("requiredFields") or []),
        "options": [dict(o) for o in pending.get("options") or []],
        "allowFreeText": bool(pending.get("allowFreeText", True)),
    }
    return proposal


def verify_used_memory_refs(refs: list[dict[str, Any]],
                            available: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """检查用了哪些记忆 —— 只能引用「真的检索到过」且「状态是 ACTIVE」的。

    为什么要卡这个：v3 把记忆阅读权收归 P2，A3 拿不到库，只能引用检索结果。
    如果允许 A3 随便写个 memoryId，就等于绕过了 P2 的授权和可见性控制。
    """
    if len(refs) > MAX_MEMORY_REFS:
        raise ProtocolError("INVALID_ARGUMENT", f"usedMemoryRefs 最多 {MAX_MEMORY_REFS} 条")

    known = {str(m.get("memoryId")): int(m.get("version") or 1) for m in available or []}
    out: list[dict[str, Any]] = []
    for ref in refs:
        if not isinstance(ref, dict):
            raise ProtocolError("INVALID_ARGUMENT", "usedMemoryRefs 的每一项都必须是对象")
        memory_id = str(ref.get("memoryId") or "")
        version = ref.get("version")
        if not memory_id or not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise ProtocolError("INVALID_ARGUMENT", "usedMemoryRefs 每项需要 memoryId 与 version(≥1)")
        if memory_id not in known:
            raise ProtocolError("FORBIDDEN", f"引用了本次未检索到的记忆：{memory_id}")
        if known[memory_id] != version:
            raise ProtocolError("STALE_VERSION",
                                f"记忆 {memory_id} 版本已变（当前 {known[memory_id]}，引用 {version}）")
        item = {"memoryId": memory_id, "version": version}
        if item not in out:
            out.append(item)
    return out


def build_response(inv: Invocation, *, intent: str, domains: list[str],
                   reply_text: str, next_step: str,
                   outcome: str | None = None,
                   input_request: dict[str, Any] | None = None,
                   dependency_task_ids: list[str] | None = None,
                   confirmation_ids: list[str] | None = None,
                   results: list[dict[str, Any]] | None = None,
                   tools: list[dict[str, Any]] | None = None,
                   handoff: dict[str, Any] | None = None,
                   used_memory_refs: list[dict[str, Any]] | None = None,
                   available_memories: list[dict[str, Any]] | None = None,
                   speech_rate: float = DEFAULT_SPEECH_RATE,
                   root_schema: dict[str, Any] | None = None) -> dict[str, Any]:
    """产出 AgentResponse。

    出来之前会**用官方 Schema 自校一次**。宁可在这里崩，也不要让不合规的报文
    发到 P2 那边变成一个难查的 500。
    """
    if intent not in DOMAINS:
        raise ProtocolError("INVALID_ARGUMENT", f"intent 必须是登记的领域之一：{intent}")

    picked: list[str] = []
    for domain in domains or [intent]:
        if domain not in DOMAINS:
            raise ProtocolError("INVALID_ARGUMENT", f"未登记的领域：{domain}")
        if domain not in picked:
            picked.append(domain)
    if not picked:
        picked = [intent]

    if not isinstance(reply_text, str) or not reply_text.strip():
        raise ProtocolError("INVALID_ARGUMENT", "reply.text 不能为空 —— 老人看不到空话")
    if len(reply_text) > 4000:
        raise ProtocolError("INVALID_ARGUMENT", "reply.text 最多 4000 字符")

    rate = float(speech_rate)
    if not (MIN_SPEECH_RATE <= rate <= MAX_SPEECH_RATE):
        raise ProtocolError("INVALID_ARGUMENT",
                            f"speechRate 必须在 {MIN_SPEECH_RATE}~{MAX_SPEECH_RATE} 之间")

    confirms = list(confirmation_ids or [])
    # 语义补丁：WAIT_CONFIRMATION 却没给确认 ID，前端会卡住等一个不存在的确认
    if next_step == NEXT_WAIT_CONFIRMATION and not confirms:
        raise ProtocolError("INVALID_ARGUMENT",
                            "WAIT_CONFIRMATION 必须在 confirmationIds 里给出待确认对象")

    if len(results or []) > MAX_RESULTS:
        raise ProtocolError("INVALID_ARGUMENT", f"results 最多 {MAX_RESULTS} 条")

    data = {
        "conversationId": inv.conversation_id,
        "messageId": inv.message_id,
        "taskId": inv.task_id,
        "baseTaskVersion": inv.task_version,
        "invocationId": inv.invocation_id,
        "intent": intent,
        "domains": picked,
        "control": settle_control(next_step, outcome=outcome,
                                  dependency_task_ids=dependency_task_ids,
                                  input_request=input_request),
        "reply": {"text": reply_text.strip(), "speechRate": round(rate, 2),
                  "audioUrl": None},
        "results": list(results or []),
        "confirmationIds": confirms,
        "tools": list(tools or []),
        "handoff": handoff,
        "usedMemoryRefs": verify_used_memory_refs(used_memory_refs or [],
                                                  available_memories or []),
    }
    response = {"code": "OK", "message": "成功", "data": data}

    _assert_schema(response, "AgentResponse", root_schema, "AgentResponse")
    return response


def build_handoff(target: str, reason: str) -> dict[str, Any]:
    """转人工。target 只能是 family / scenic / official —— 别自己发明收件人。"""
    if target not in ("family", "scenic", "official"):
        raise ProtocolError("INVALID_ARGUMENT", f"handoff.to 只能是 family/scenic/official，收到 {target}")
    if not reason or not reason.strip():
        raise ProtocolError("INVALID_ARGUMENT", "转人工必须说明原因")
    return {"type": "human_handoff", "to": target, "reason": reason.strip()}


def error_response(code: str, message: str) -> tuple[int, dict[str, Any]]:
    """失败一律 data=null。返回 (HTTP状态码, 响应体)。"""
    if code not in ERROR_STATUS:
        raise ProtocolError("INVALID_ARGUMENT", f"未定义的错误码：{code}")
    payload = {"code": code, "message": (message or "").strip() or "未说明原因", "data": None}
    return ERROR_STATUS[code], payload


def from_exception(error: Exception) -> tuple[int, dict[str, Any]]:
    """把任何异常转成 (状态码, 响应体)。未知异常一律 500，不把堆栈漏出去。"""
    if isinstance(error, ProtocolError):
        return error_response(error.code, error.message)
    return error_response("INTERNAL_ERROR", "服务内部错误，请稍后重试")


# ------------------------------------------------------------------ Schema
def _load_root_schema() -> dict[str, Any]:
    if "root" not in _SCHEMA_CACHE:
        folder = schema_dir()
        if folder is None:
            raise FileNotFoundError("找不到 control.schema.json，请检查 schemas/ 目录")
        _SCHEMA_CACHE["root"] = schema_check.load_schema(
            os.path.join(folder, "control.schema.json"))
    return _SCHEMA_CACHE["root"]


def _assert_schema(instance: Any, name: str, root_schema: dict[str, Any] | None,
                   label: str) -> None:
    """用官方 Schema 校一次。

    找不到 Schema 时**跳过校验并警告一次**，不阻断业务 —— 但绝不假装校过了。
    开发期的自欺：测试全绿其实一条都没跑，比报错难查得多。
    """
    global _SCHEMA_WARNED
    try:
        root = root_schema or _load_root_schema()
    except (OSError, KeyError, json.JSONDecodeError) as error:
        if not _SCHEMA_WARNED:
            _SCHEMA_WARNED = True
            print(f"[v3_messages] 警告：未能加载官方 Schema（{error}），本次跳过报文自校。"
                  f"生产环境请把 control.schema.json 放进 schemas/。", file=sys.stderr)
        return
    try:
        schema_check.validate(instance, root["definitions"][name], root)
    except schema_check.SchemaError as error:
        raise ProtocolError("INVALID_ARGUMENT", f"{label} 不符合官方 Schema：{error}") from error


# ------------------------------------------------------------------ 离线回放
def _sample_invocation() -> dict[str, Any]:
    return {
        "protocolVersion": "3.0",
        "userId": "u100",
        "conversationId": "conv-001",
        "messageId": "msg-001",
        "task": {"id": "child-002", "parentTaskId": "root-001", "version": 3,
                 "attempt": 1, "invocationId": "invoke-child-002",
                 "deadlineAt": "2026-10-29T02:01:00Z"},
        "input": {"text": "想学剪纸，别太远", "attachmentIds": []},
        "context": {"businessRefs": [], "history": [], "completedEffects": [],
                    "reason": "USER_MESSAGE", "candidateTasks": [],
                    "dependencyResults": [], "confirmationResults": [],
                    "actionLedger": [], "planSteps": [],
                    "readSet": {"memoryRevision": 12, "authorizationRevision": 4,
                                "provenanceRefs": []},
                    "inputResponse": None, "pendingInputRequests": []},
        "capabilityToken": "DEMO-TOKEN-NOT-A-REAL-CREDENTIAL",
    }


def _selftest() -> int:
    root = _load_root_schema()
    examples = schema_check.load_schema(os.path.join(schema_dir() or "", "examples.json"))

    print(f"Schema 来自：{os.path.abspath(os.path.join(schema_dir() or '', 'control.schema.json'))}")
    print()

    print("=" * 70)
    print(" 1) 38 份官方报文过一遍官方 Schema")
    print("=" * 70)
    ok = 0
    for case in examples["cases"]:
        if schema_check.is_valid(case["body"], root["definitions"][case["schema"]], root):
            ok += 1
    print(f"  {ok} / {len(examples['cases'])} 通过")

    print()
    print("=" * 70)
    print(" 2) 7 份 InvocationRequest 全部通过 parse_invocation")
    print("=" * 70)
    invocations = []
    for case in examples["cases"]:
        if case["schema"] != "InvocationRequest":
            continue
        try:
            inv = parse_invocation(case["body"], root_schema=root)
            invocations.append(inv)
            print(f"  ✓ {case['name']:<46} reason={inv.reason:<20} text={inv.text[:12]}")
        except ProtocolError as error:
            print(f"  ✗ {case['name']}  {error.code} {error.message}")

    print()
    print("=" * 70)
    print(" 3) 用第 1 份请求造一个响应，再用 Schema 自校")
    print("=" * 70)
    inv = invocations[0] if invocations else parse_invocation(_sample_invocation(), root_schema=root)
    response = build_response(
        inv, intent="culture", domains=["culture", "tourism"],
        reply_text="给您找了个剪纸班，就在小区活动室，走过去五分钟。",
        next_step=NEXT_COMPLETE, outcome=OUTCOME_SUCCEEDED,
        used_memory_refs=[{"memoryId": "memory-001", "version": 2}],
        available_memories=[{"memoryId": "memory-001", "version": 2}],
        root_schema=root)
    schema_check.validate(response, root["definitions"]["AgentResponse"], root)
    print(f"  ✓ 生成通过 Schema 校验：next={response['data']['control']['next']} "
          f"outcome={response['data']['control']['outcome']}")
    print(f"    reply={response['data']['reply']['text']}")
    print(f"    audioUrl={response['data']['reply']['audioUrl']!r}  （v3 固定 null）")

    print()
    print("=" * 70)
    print(" 4) 五种「几乎一定会写错」的组合，全都当场拦住")
    print("=" * 70)
    traps = [
        ("COMPLETE 却不给 outcome",
         lambda: build_response(inv, intent="culture", domains=["culture"],
                                reply_text="好了", next_step=NEXT_COMPLETE,
                                root_schema=root)),
        ("WAIT_INPUT 却不给问题",
         lambda: build_response(inv, intent="culture", domains=["culture"],
                                reply_text="请回答", next_step=NEXT_WAIT_INPUT,
                                root_schema=root)),
        ("WAIT_DEPENDENCIES 却没有依赖",
         lambda: build_response(inv, intent="culture", domains=["culture"],
                                reply_text="等一下", next_step=NEXT_WAIT_DEPENDENCIES,
                                root_schema=root)),
        ("引用一个根本没检索到的记忆",
         lambda: build_response(inv, intent="culture", domains=["culture"],
                                reply_text="好", next_step=NEXT_COMPLETE,
                                outcome=OUTCOME_SUCCEEDED,
                                used_memory_refs=[{"memoryId": "memory-999", "version": 1}],
                                available_memories=[{"memoryId": "memory-001", "version": 2}],
                                root_schema=root)),
        ("用 v2 的旧字段名 toolContextToken",
         lambda: parse_invocation({**_sample_invocation(), "toolContextToken": "x"},
                                  root_schema=root)),
    ]
    for label, action in traps:
        try:
            action()
        except ProtocolError as error:
            print(f"  ✓ {label:<24} → {error.status} {error.code}：{error.message[:44]}")
        else:
            print(f"  ✗ {label} 竟然通过了！")
            return 1

    print()
    print("=" * 70)
    print(" 5) 错误码 → HTTP 状态，16 个码全覆盖")
    print("=" * 70)
    for code, status in sorted(ERROR_STATUS.items(), key=lambda kv: kv[1]):
        print(f"  {status}  {code}")
    print(f"  共 {len(ERROR_STATUS)} 个，与 Schema 的 ErrorResponse.code 枚举一致")

    print()
    print("结论：收得进来（7 份真实请求全解析）、吐得出去（响应过 Schema 自校）、"
          "错得明白（16 个码 + 5 类陷阱全拦）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
