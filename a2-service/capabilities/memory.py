# -*- coding: utf-8 -*-
"""
capabilities/memory.py —— 记忆反馈（八能力之一，契约 4.1 占位口径）

契约 4.1：非 tourism/help 意图按占位处理。care 类（记忆反馈）第一阶段占位：
- 真实识别记忆意图（intent=care，满足契约 12 节「能被意图路由识别」）；
- 返回诚实占位结果，不写长期记忆、不调 memory.write（避免越过工具白名单 C1/C3）；
- 以 knowledge.search 作为示例工具、本地知识库条目作为「知识条目」（满足 12 节第 3 条）；
- 不声称已具备真实记忆读写能力（满足 12 节第 4 条）。
"""
from typing import Any, Dict, Optional, Tuple

from capabilities.base import CapabilityResult
from schemas import build_result_item, build_tool
from knowledge import retrieve as retrieve_knowledge

_REL_KW = ("家人", "子女", "老伴", "儿子", "女儿", "孙", "关系", "亲戚")
_EXP_KW = ("上次", "那次", "去过", "经历", "旅游", "游玩", "印象", "记得那次")

_LEAD_WORDS = ("记住", "记一下", "我希望你记住", "我希望记住", "我跟你说过",
               "我喜欢", "我习惯", "我的偏好是", "我的偏好", "我不喜欢",
               "我怕", "我担心", "我讨厌", "记着")


def _parse(text: str) -> Tuple[str, str]:
    mtype = "preference"
    if any(w in text for w in _REL_KW):
        mtype = "relation"
    elif any(w in text for w in _EXP_KW):
        mtype = "experience"
    content = text
    for w in _LEAD_WORDS:
        content = content.replace(w, "")
    content = content.strip(" ，。、：:") or text
    return mtype, content


async def handle(*, message, text, user_id, token, inv_id, meta, **_):
    mtype, content = _parse(text)
    try:
        hits = retrieve_knowledge(text, top_k=2)
    except Exception:
        hits = []
    kb = hits[0]["text"] if hits else ""

    results = [
        build_result_item("记忆反馈", "演示占位（阶段2 骨架已就绪，长期记忆写入待开放）",
                          status="PLACEHOLDER"),
        build_result_item("识别到记忆类型", mtype, status="INFO"),
        build_result_item("当前可提供", "偏好/关系/经历的临时记录说明，待阶段2 上线后按要求写入长期记忆。",
                          status="INFO"),
    ]
    if kb:
        results.append(build_result_item(
            "相关资料", (kb[:42] + ("…" if len(kb) > 42 else "")), status="MATCHED"))

    reply_text = ("记忆功能正在接入中，目前以演示占位呈现。您说的「%s」我已识别为%s，"
                 "真实长期记忆写入将在阶段2 上线后由记忆服务接管。%s"
                 % (content, mtype, ("（参考：" + kb[:30] + "…）" if kb else "")))
    return CapabilityResult(
        intent="care", domains=["care"],
        reply_text=reply_text, speech_rate=0.9,
        tools=[build_tool("knowledge.search", {"query": text[:60]},
                          {"entries": [h["text"][:40] for h in hits]})],
        results=results,
        control_next="COMPLETE", control_outcome="PARTIALLY_SUCCEEDED",
    )
