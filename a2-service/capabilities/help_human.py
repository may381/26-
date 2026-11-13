# -*- coding: utf-8 -*-
"""
capabilities/help_human.py —— 求助与人工（八能力之一，唯一走 P2 全链路的能力）

这是 A2 的旗舰能力：老人发起求助 -> P2 按关键词路由到 a2 -> 本 handler 调真实大模型 + RAG + 可选 MCP 建单，
并如实填充契约结构化字段：
- handoff：老人明确紧急/求助时，转人工（scenic 景区 / family 家属），附 reason。
- results：结构化求助处理计划（已通知 / 处理建议 / 匹配状态）。
- usedMemoryRefs：若引用了已知长期偏好（演示占位，后续接记忆库）。
"""
from typing import Any, Dict, Optional

from capabilities._core import run_llm_pipeline
from capabilities.base import CapabilityResult
from schemas import build_handoff, build_result_item
from metrics import metrics

# 触发「转人工」的关键词（明确需要人介入）
_HUMAN_HANDOFF_KW = ("求助", "报警", "120", "救命", "晕", "摔", "紧急",
                     "需要人帮忙", "工作人员", "叫人", "快来",
                     "迷路", "走散", "走不动", "急需帮助", "需要帮助",
                     "帮帮我", "不舒服", "难受", "危险", "害怕")
# 转家属（而非景区）的线索
_FAMILY_HANDOFF_KW = ("家人", "子女", "老伴", "儿子", "女儿", "通知家属", "联系家里")


async def handle(*, message, text, user_id, token, inv_id, meta, **_):
    pipe = await run_llm_pipeline(text=text, user_id=user_id, token=token,
                                 inv_id=inv_id, intent="help")
    tools = pipe["tools"]
    reply_text = pipe["reply_text"]
    speech_rate = pipe["speech_rate"]

    handoff = None
    results: list = []

    # 转人工：老人明确紧急/求助
    if any(k in text for k in _HUMAN_HANDOFF_KW):
        to = "family" if any(k in text for k in _FAMILY_HANDOFF_KW) else "scenic"
        who = "家属" if to == "family" else "景区工作人员"
        reason = "老人发起求助，需要%s介入协助" % who
        handoff = build_handoff(to, reason)
        metrics.inc("handoffs")
        results.append(build_result_item(
            "已通知", "已向%s发出协助请求，请保持原地等待" % who,
            status="DISPATCHED"))
    # 结构化求助处理计划（无论是否转人工都给建议）
    results.append(build_result_item(
        "处理建议", "保持原地、避免走动，等待工作人员到位", status="SUGGESTED"))
    results.append(build_result_item(
        "匹配状态", "现场响应已触发" if handoff else "AI 已安抚并给出建议",
        status="MATCHED" if handoff else "AI_HANDLED"))

    return CapabilityResult(
        intent="help",
        domains=["help", "care"],
        reply_text=reply_text,
        speech_rate=speech_rate,
        tools=tools,
        handoff=handoff,
        results=results,
        used_memory_refs=[],  # 后续接记忆库后可引用已知偏好（如避台阶）
    )
