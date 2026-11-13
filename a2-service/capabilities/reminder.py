# -*- coding: utf-8 -*-
"""
capabilities/reminder.py —— 健康提醒（八能力之一，契约 4.1 占位口径）

契约 4.1 明文：非 tourism/help 的意图「必须能被识别，并返回统一的『该服务暂未开放』
或演示占位结果」。第一阶段仅 tourism+help 真做，health 类（含健康提醒）按占位处理：
- 真实识别健康提醒意图（intent=health，满足契约 12 节「能被意图路由识别」）；
- 返回诚实占位结果，不落库、不调 memory.write（避免越过工具白名单 C1/C3）；
- 以 knowledge.search 作为示例工具、并以本地知识库条目作为「知识条目」（满足 12 节第 3 条）；
- 不声称已具备真实提醒服务能力（满足 12 节第 4 条）。
"""
import re
from typing import Any, Dict, Optional, Tuple

from capabilities.base import CapabilityResult
from schemas import build_result_item, build_tool
from knowledge import retrieve as retrieve_knowledge

_MED_KW = ("吃药", "用药", "服药", "药", "体检", "复查", "复诊", "血压", "血糖", "量血压")
_TIME_KW = ("提醒", "几点", "吃药", "用药", "服药", "复查", "体检", "复诊",
            "日程", "闹钟", "别忘了", "记一下时间", "约定", "什么时候")

_TIME_RE = re.compile(
    r"(上午|下午|早上|晚上|中午|傍晚)?\s*"
    r"(\d{1,2})\s*(点|时|：|:)\s*(\d{0,2})"
)


def _parse(text: str) -> Tuple[str, Optional[str], str]:
    rtype = "MEDICATION" if any(w in text for w in _MED_KW) else "SCHEDULE"
    m = _TIME_RE.search(text)
    remind_at = None
    if m:
        period = m.group(1) or ""
        hh = m.group(2)
        mm = m.group(4) or "00"
        remind_at = "%s%s:%s" % (period, hh, mm)
    # 事项：去掉引导词与时间表达
    content = text
    for w in ("提醒我", "帮我提醒", "提醒一下", "提醒", "记得", "我想", "我要", "请帮我", "帮我"):
        content = content.replace(w, "")
    content = re.sub(r"(上午|下午|早上|晚上|中午|傍晚)?\s*\d{1,2}\s*(点|时|：|:)\s*\d{0,2}", "", content)
    content = content.strip(" ，。、：:") or text
    return rtype, remind_at, content


async def handle(*, message, text, user_id, token, inv_id, meta, **_):
    # 真实识别意图并抽取事项（用于知识检索与占位说明），但第一阶段不落库。
    rtype, remind_at, content = _parse(text)
    try:
        hits = retrieve_knowledge(text, top_k=2)
    except Exception:
        hits = []
    kb = hits[0]["text"] if hits else ""

    results = [
        build_result_item("健康提醒", "演示占位（阶段2 骨架已就绪，真实提醒计划待开放）",
                          status="PLACEHOLDER"),
        build_result_item("识别到事项", content, status="INFO"),
        build_result_item("当前可提供", "用药/复查提醒的接入说明与适老健康提示，待阶段2 上线后由本地提醒服务接管。",
                          status="INFO"),
    ]
    if kb:
        results.append(build_result_item(
            "相关健康提示", (kb[:42] + ("…" if len(kb) > 42 else "")), status="MATCHED"))

    reply_text = ("健康提醒功能正在接入中，目前以演示占位呈现。您提到的「%s」我已识别，"
                 "真实用药/复查提醒计划将在阶段2 上线后由本地提醒服务接管。%s"
                 % (content, ("（参考：" + kb[:30] + "…）" if kb else "")))
    return CapabilityResult(
        intent="health", domains=["health"],
        reply_text=reply_text, speech_rate=1.0,
        tools=[build_tool("knowledge.search", {"query": text[:60]},
                          {"entries": [h["text"][:40] for h in hits]})],
        results=results,
        control_next="COMPLETE", control_outcome="PARTIALLY_SUCCEEDED",
    )
