# -*- coding: utf-8 -*-
"""
schemas.py —— v3 协议数据模型（方案 B：模板 C 入站 / 模板 D 出站）
===============================================================
严格对齐《Agent 统一交互协议 v3.0》以及《底座契约_v1》4.2~4.4 节：
  - 入站（模板 C）：P2 派活请求体。字段较多且随版本演进，这里用宽松模型（允许额外字段）。
  - 出站（模板 D）：A2 返回的结果单。P2 的 responseChecks.validate() 要求【恰好 14 个】顶层字段，
    少一个/多一个都会抛 IllegalArgumentException 被拒。因此 ResultSheet 的字段、命名、数量必须一一对应。

注意：出站字段必须包含 intent / domains / handoff 三个易漏字段，且 taskId/baseTaskVersion/
invocationId/conversationId/messageId 必须【原样回传】P2 下发的任务标识，否则 finish() 判
Mismatched invocation 拒收。

契约 4.2~4.4 关键结构（A2 结果单现在如实填充）：
  - tools（4.2）：对象数组，每项 {tool, args, result}；工具名取契约枚举
                 knowledge.search / help.create / memory.write / route.recommend。
  - handoff（4.3）：{type:"human_handoff", to:"family|scenic|official", reason:"…"}，无则 null。
  - usedMemoryRefs（4.4）：[{memoryId, type:"preference|experience|relation|serviceRecord",
                            content, version}]，引用已写入的长期记忆。
  - results（路线/候选/建议）：结构化结果数组，每条带 label/value/status/candidates/note。
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# 入站（模板 C）：P2 -> A2 的派活请求
# ---------------------------------------------------------------------------
class DispatchRequest(BaseModel):
    model_config = ConfigDict(extra="allow")  # 允许协议未来扩展字段，不丢数据

    protocolVersion: str = "3.0"
    intent: Optional[str] = None              # 可选：P2 下发的意图（A2 也可自识别）
    userId: Optional[str] = None
    conversationId: Optional[str] = None
    messageId: Optional[str] = None
    input: Optional[Dict[str, Any]] = None          # {text, attachmentIds, ...}
    task: Optional[Dict[str, Any]] = None           # {id, parentTaskId, version, invocationId, deadlineAt}
    context: Optional[Dict[str, Any]] = None
    capabilityToken: Optional[str] = None           # P2 下发的调用凭证（A2 调 P2 工具时回传）


# ---------------------------------------------------------------------------
# 出站（模板 D）：A2 -> P2 的结果单（恰好 14 个顶层字段）
# ---------------------------------------------------------------------------
class ToolCall(BaseModel):
    """契约 4.2 工具调用记录：工具名 + 入参 + 返回（A2 如实声明实际调用）。"""
    tool: str
    args: Dict[str, Any] = {}
    result: Optional[Dict[str, Any]] = None


class ReplyBlock(BaseModel):
    text: str
    speechRate: float
    audioUrl: Optional[str] = None


class ControlBlock(BaseModel):
    next: str = "COMPLETE"             # COMPLETE / WAIT_INPUT / WAIT_CONFIRMATION / WAIT_DEPENDENCIES
    outcome: Optional[str] = "SUCCEEDED"  # SUCCEEDED / FAILED / null(等待分支，契约样例 03/04)
    inputRequest: Optional[Any] = None
    dependencyTaskIds: List[str] = []


class ResultSheet(BaseModel):
    # —— 任务标识（必须原样回传 P2 下发的）——
    intent: str
    domains: List[str]
    taskId: Optional[str] = None
    baseTaskVersion: Optional[int] = None
    invocationId: Optional[str] = None
    conversationId: Optional[str] = None
    messageId: Optional[str] = None
    # —— 回复与流程控制 ——
    reply: ReplyBlock
    control: ControlBlock
    # —— 声明与引用（契约 4.2~4.4）——
    confirmationIds: List[str] = []
    tools: List[ToolCall] = []         # 契约对象数组，非字符串
    usedMemoryRefs: List[Any] = []
    handoff: Optional[Any] = None       # 易漏字段：无 handoff 时显式 null
    results: List[Any] = []


# ---------------------------------------------------------------------------
# 便捷构造器（让业务层用起来像搭积木，避免到处手写 dict）
# ---------------------------------------------------------------------------
def build_tool(tool: str, args: Optional[Dict[str, Any]] = None,
               result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """构造一条契约 4.2 工具记录。"""
    return {"tool": tool, "args": args or {}, "result": result or {}}


def build_handoff(to: str, reason: str, htype: str = "human_handoff") -> Dict[str, Any]:
    """构造契约 4.3 转人工事件。to ∈ family / scenic / official。"""
    return {"type": htype, "to": to, "reason": reason}


def build_memory_ref(memory_id: str, mtype: str, content: str,
                     version: int = 1) -> Dict[str, Any]:
    """构造契约 4.4 记忆引用。type ∈ preference/experience/relation/serviceRecord。"""
    return {"memoryId": memory_id, "type": mtype, "content": content, "version": version}


def build_result_item(label: str, value: str, status: Optional[str] = None,
                      candidates: Optional[List[Dict[str, Any]]] = None,
                      note: Optional[str] = None) -> Dict[str, Any]:
    """构造一条结构化结果（建议/依据/候选/匹配状态/待确认事项）。
    - label：这一项的主题（如「已通知」「建议」「候选」「匹配状态」「待确认事项」）
    - value：一句话结论
    - status：可选状态（如 MATCHED / PENDING / SUGGESTED）
    - candidates：可选候选列表（如多条候选路线/方案）
    - note：补充说明
    """
    item: Dict[str, Any] = {"label": label, "value": value}
    if status is not None:
        item["status"] = status
    if candidates is not None:
        item["candidates"] = candidates
    if note is not None:
        item["note"] = note
    return item


def build_result_sheet(
    *,
    meta: Dict[str, Any],
    reply_text: str,
    speech_rate: float = 0.8,
    intent: str = "care",
    domains: Optional[List[str]] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    handoff: Optional[Any] = None,
    results: Optional[List[Any]] = None,
    used_memory_refs: Optional[List[Any]] = None,
    confirmation_ids: Optional[List[str]] = None,
    input_request: Optional[Any] = None,
    control_next: str = "COMPLETE",
    control_outcome: str = "SUCCEEDED",
    dependency_task_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """便捷构造模板 D 结果单（dict 形态，供 main.py 直接返回）。

    关键约束：返回 dict 必须恰好 14 个顶层字段（与 ResultSheet 模型一致），
    否则 P2.responseChecks 拒收。新增的结构化内容走 handoff/results/usedMemoryRefs/
    confirmationIds/control.inputRequest，不新增顶层字段。
    """
    sheet = ResultSheet(
        intent=intent,
        domains=domains or ["care"],
        taskId=meta.get("taskId"),
        baseTaskVersion=meta.get("baseTaskVersion"),
        invocationId=meta.get("invocationId"),
        conversationId=meta.get("conversationId"),
        messageId=meta.get("messageId"),
        reply=ReplyBlock(text=reply_text, speechRate=speech_rate, audioUrl=None),
        control=ControlBlock(
            next=control_next,
            outcome=control_outcome,
            inputRequest=input_request,
            dependencyTaskIds=dependency_task_ids or [],
        ),
        confirmationIds=confirmation_ids or [],
        tools=[(ToolCall(**t) if not isinstance(t, ToolCall) else t) for t in (tools or [])],
        usedMemoryRefs=used_memory_refs or [],
        handoff=handoff,
        results=results or [],
    )
    return sheet.model_dump()
