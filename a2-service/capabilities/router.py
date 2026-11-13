# -*- coding: utf-8 -*-
"""
capabilities/router.py —— 能力路由与分发入口

- detect_capability：支持「P2 下发 intent」或「A2 自识别（关键词）」两种方式。
- dispatch：统一入口，做输入护栏 + 指标埋点 + 分发到对应 handler，返回模板 D 结果单。

能力注册表（八项业务能力）：
  help_human      求助与人工（走 P2 全链路）
  health_reminder 健康提醒
  memory_feedback 记忆反馈
  health_life     健康生活（占位）
  family_care     家庭照护（占位）
  family_coord    家庭协同（占位）
  community       社区活动（占位）
  volunteer       志愿服务（占位）
"""
import logging
from typing import Any, Dict, Optional, Tuple

from guardrails import scan_input, decide_refusal
from metrics import metrics
from capabilities.base import CapabilityResult
from capabilities import help_human, reminder, memory, placeholder

logger = logging.getLogger("a2")

# 关键词（A2 自识别用）
_REMINDER_KW = ("提醒", "几点", "吃药", "用药", "服药", "复查", "体检", "复诊",
                "日程", "闹钟", "别忘了", "记一下时间", "什么时候", "几点了")
_MEMORY_KW = ("记住", "我记得", "我喜欢", "我习惯", "我的偏好", "记一下",
              "我怕", "我担心", "我不喜欢", "我讨厌", "记着", "我跟你说过")
_COMMUNITY_KW = ("社区", "邻里", "小区", "居委会", "活动中心")
_VOLUNTEER_KW = ("志愿", "义工", "帮扶", "做公益", "公益", "助老", "志愿者")
_FAMILY_KW = ("家人", "子女", "老伴", "儿子", "女儿", "照护", "照顾", "儿女", "亲戚", "家属")

# 能力注册表：key -> handler（具名函数，便于 demo 直接调用）
REGISTRY = {
    "help_human": help_human.handle,
    "health_reminder": reminder.handle,
    "memory_feedback": memory.handle,
    "health_life": placeholder.handle_health_life,
    "family_care": placeholder.handle_family_care,
    "family_coord": placeholder.handle_family_coord,
    "community": placeholder.handle_community,
    "volunteer": placeholder.handle_volunteer,
}


def detect_capability(text: str, explicit_intent: Optional[str]) -> str:
    """返回能力 key。优先用 P2 下发的 intent；否则按文本关键词识别。"""
    t = (text or "")

    # 1) 显式 intent 映射
    if explicit_intent:
        e = explicit_intent.lower()
        if e in ("help",):
            return "help_human"
        if e in ("health",):
            return "health_reminder" if any(k in t for k in _REMINDER_KW) else "health_life"
        if e in ("memory", "memory_feedback"):
            return "memory_feedback"
        if e in ("community",):
            return "community"
        if e in ("volunteer",):
            return "volunteer"
        if e in ("ability", "family_care"):
            return "family_care"
        if e in ("care", "family_coord"):
            return "help_human" if any(k in t for k in ("求助", "帮助", "迷路", "急", "不舒服", "需要人")) else "family_coord"
        # 其它（tourism/fraud/culture 等）落入兜底
        return "help_human"

    # 2) 关键词自识别
    if any(k in t for k in _MEMORY_KW):
        return "memory_feedback"
    if any(k in t for k in _REMINDER_KW):
        return "health_reminder"
    if any(k in t for k in _COMMUNITY_KW):
        return "community"
    if any(k in t for k in _VOLUNTEER_KW):
        return "volunteer"
    if any(k in t for k in _FAMILY_KW):
        return "family_care"
    # 默认：求助与人工（care 域）
    return "help_human"


async def dispatch(message: Dict[str, Any]) -> Dict[str, Any]:
    """A2 能力分发统一入口，返回模板 D 结果单（dict，恰好 14 字段）。"""
    text = (message.get("input") or {}).get("text", "")
    token = message.get("capabilityToken", "")
    user_id = message.get("userId")
    task = message.get("task") or {}
    meta = {
        "taskId": task.get("id"),
        "baseTaskVersion": task.get("version"),
        "invocationId": task.get("invocationId"),
        "conversationId": message.get("conversationId"),
        "messageId": message.get("messageId"),
    }
    inv_id = meta.get("invocationId") or ""
    explicit = message.get("intent")

    metrics.inc("requests_total")

    # 1) 输入护栏（注入/越狱）
    inscan = scan_input(text)
    if inscan.flagged:
        metrics.inc("guardrail_input_flagged")
        metrics.inc("refusals")
        cap = CapabilityResult(
            intent="care", domains=["care"],
            reply_text=decide_refusal(inscan), tools=[],
        )
        return cap.to_sheet(meta)

    # 2) 路由分发
    key = detect_capability(text, explicit)
    handler = REGISTRY.get(key, help_human.handle)
    cap: CapabilityResult = await handler(
        message=message, text=text, user_id=user_id,
        token=token, inv_id=inv_id, meta=meta,
    )
    metrics.record_intent(cap.intent)
    if cap.handoff:
        metrics.inc("handoffs")

    return cap.to_sheet(meta)
