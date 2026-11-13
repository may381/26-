# -*- coding: utf-8 -*-
"""
capabilities/placeholder.py —— 其余 5 项能力（契约 4.1 占位实现）

契约 4.1 明文：非 tourism/help 的意图「必须能被识别，并返回统一的『该服务暂未开放』
或演示占位结果」。因此这 5 项走"真实识别 + 结构化占位"路径：
- 健康生活 / 家庭照护 / 家庭协同 / 社区活动 / 志愿服务
- 从本地知识库检索相关内容（若有）作为「匹配内容」，并明确标注服务处于演示阶段。
严格要求：不假装已提供真实服务，reply 与 results 均如实说明占位状态。
"""
from typing import Any, Dict, Optional

from capabilities.base import CapabilityResult
from schemas import build_result_item
from knowledge import retrieve as retrieve_knowledge

# key -> (intent, domains, 服务名, 演示占位说明)
_PLACEHOLDER_INFO: Dict[str, tuple] = {
    "health_life": ("health", ["health"], "健康生活",
                    "日常健康小贴士与适老运动建议，后续将接入健康档案与体征监测。"),
    "family_care": ("ability", ["ability", "care"], "家庭照护",
                    "面向家属的远程照护与异常提醒，后续将接入家属协同看板。"),
    "family_coord": ("care", ["care"], "家庭协同",
                     "家属共享老人行程与位置授权，后续将接入家庭关系绑定。"),
    "community": ("community", ["community"], "社区活动",
                  "周边社区适老活动与邻里互助，后续将接入社区活动日历。"),
    "volunteer": ("volunteer", ["volunteer"], "志愿服务",
                  "景区志愿者帮扶与公益陪伴，后续将接入志愿调度。"),
}


def _make_handler(key: str):
    async def handler(*, message, text, user_id, token, inv_id, meta, **_):
        intent, domains, name, desc = _PLACEHOLDER_INFO[key]
        hits = retrieve_knowledge(text, top_k=2)
        kb = hits[0]["text"] if hits else ""
        results = [
            build_result_item("服务状态", "演示占位（阶段2 骨架已就绪，真实服务待开放）",
                              status="PLACEHOLDER"),
            build_result_item("当前可提供", desc, status="INFO"),
        ]
        if kb:
            results.append(build_result_item(
                "相关资料", (kb[:42] + ("…" if len(kb) > 42 else "")), status="MATCHED"))
        reply_text = "您提到的%s服务，目前处于演示阶段，我先为您记下需求：%s%s" % (
            name, desc, ("（参考：" + kb[:30] + "…）" if kb else ""))
        return CapabilityResult(
            intent=intent, domains=domains,
            reply_text=reply_text, speech_rate=0.9, results=results,
        )
    return handler


# 导出 5 个具名 handler
handle_health_life = _make_handler("health_life")
handle_family_care = _make_handler("family_care")
handle_family_coord = _make_handler("family_coord")
handle_community = _make_handler("community")
handle_volunteer = _make_handler("volunteer")
