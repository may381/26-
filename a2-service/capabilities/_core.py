# -*- coding: utf-8 -*-
"""
capabilities/_core.py —— 能力共用管线（护栏→缓存→RAG→MCP→真实大模型→输出护栏）

所有能力 handler 共用这一段，保证：
- 指标口径一致（缓存命中率 / LLM 成功率 / 工具调用 / 护栏触发）。
- 可被测试 monkeypatch：LLM/P2 工具通过延迟导入的 agent_logic.call_llm / agent_logic.call_p2_tool 调用，
  测试里 `agent_logic.call_llm = fake` 即可生效，无需真实大模型。
- 输出始终符合契约：PII 脱敏 / 内部 token 防泄露 / 医疗处方拦截 / 跨用户隔离。
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional

from schemas import build_tool
from guardrails import scan_input, scan_output, check_scope
from cache import cache
from metrics import metrics
from knowledge import retrieve as retrieve_knowledge
from mcp_client import get_client as get_mcp_client

logger = logging.getLogger("a2")

_TICKET_KEYWORDS = ("建单", "工单", "报修", "投诉", "登记求助", "帮我登记",
                    "开个工单", "帮我建", "提交工单", "创建工单")


def _wants_ticket(text: str) -> bool:
    return bool(text) and any(k in text for k in _TICKET_KEYWORDS)


async def run_llm_pipeline(
    *,
    text: str,
    user_id: Optional[str],
    token: str,
    inv_id: str,
    intent: str = "care",
    extra_context: Optional[str] = None,
) -> Dict[str, Any]:
    """共用推理管线。返回 {reply_text, speech_rate, tools, rag_hits, ticket_id, from_cache}。

    LLM / P2 工具通过 agent_logic 的模块属性调用，以便测试打桩。
    """
    # 延迟导入：agent_logic.call_llm / call_p2_tool 可被测试 monkeypatch
    from agent_logic import call_llm, call_p2_tool

    used_tools: List[Dict[str, Any]] = []

    # 1) 缓存（降本）
    cached = cache.get(intent, text)
    if cached is not None:
        metrics.inc("cache_hits")
        reply_text, speech_rate = cached
        return {"reply_text": reply_text, "speech_rate": speech_rate,
                "tools": [], "rag_hits": 0, "ticket_id": None, "from_cache": True}
    metrics.inc("cache_misses")

    # 2) 本地 RAG 知识检索（不依赖 P2）
    rag_hits = retrieve_knowledge(text, top_k=3)
    rag_context = ""
    if rag_hits:
        metrics.inc("rag_hits")
        rag_context = "\n".join("[%s] %s" % (h["source"], h["text"]) for h in rag_hits)

    # 3) 建工单意图 -> 经 MCP 调外部工具（不碰 P2）
    ticket_id = None
    if _wants_ticket(text):
        try:
            mcp = get_mcp_client()
            result = await asyncio.to_thread(mcp.create_ticket, "老人求助：" + text[:50], text[:200])
            if result and result.get("ticketId"):
                ticket_id = result["ticketId"]
                metrics.inc("tool_calls")
                used_tools.append(build_tool("help.create", {"summary": text[:50]},
                                             {"ticketId": ticket_id}))
        except Exception as exc:
            logger.warning("MCP 建单失败：%s", exc)

    # 组合注入 LLM 的上下文
    llm_ctx_parts = [p for p in [rag_context, extra_context] if p]
    if ticket_id:
        llm_ctx_parts.append(
            "【已为用户创建工单，编号：%s，请在回复中自然告知用户该编号】" % ticket_id
        )
    llm_ctx = "\n".join(llm_ctx_parts) or None

    # 4) 真实大模型（含主/备模型路由）
    llm, llm_err = await call_llm(text, context=llm_ctx)
    if llm:
        metrics.inc("llm_calls")
        metrics.inc("llm_ok")
        reply_text = llm["reply"]
        speech_rate = llm["speechRate"]
        if rag_hits:
            used_tools.append(build_tool("knowledge.search",
                                         {"query": text[:60]},
                                         {"hits": len(rag_hits)}))
    else:
        metrics.inc("llm_calls")
        metrics.inc("llm_fail")
        if rag_hits:
            # RAG 兜底
            metrics.inc("tool_calls")
            snippet = rag_hits[0]["text"]
            reply_text = snippet[:55] + ("……" if len(snippet) > 55 else "")
            used_tools.append(build_tool("knowledge.search",
                                         {"query": text[:60]},
                                         {"hits": len(rag_hits)}))
            if ticket_id:
                reply_text = (reply_text + "（工单编号：%s）" % ticket_id)[:60]
        else:
            # 兜底调 P2 knowledge.search
            data, err = await call_p2_tool(
                "knowledge.search",
                {"query": (text or "老人出行")[:200], "intent": "help"},
                token, inv_id,
            )
            if err is None and data:
                metrics.inc("tool_calls")
                try:
                    entries = (data.get("result") or {}).get("entries") or \
                              (data.get("result") or {}).get("items") or []
                    titles = "、".join(e.get("title", "") for e in entries[:3] if e.get("title"))
                    reply_text = ("为您查到相关资讯：%s。" % titles) if titles else "已为您检索相关资讯。"
                except Exception:
                    reply_text = "已为您检索相关资讯。"
                used_tools.append(build_tool("knowledge.search", {"query": text[:60]}, {"entries": titles}))
            else:
                reply_text = "已收到您的诉求，我正在为您跟进处理，请稍候。"

    # 5) 输出护栏（PII 脱敏 / 内部 token 防泄露 / 医疗处方拦截 / 超长截断）
    outscan = scan_output(reply_text, user_text=text)
    if outscan.flagged:
        metrics.inc("guardrail_output_flagged")
        reply_text = outscan.sanitized or "已收到您的诉求，我正在为您跟进处理，请稍候。"
        speech_rate = 0.8
    # ⑤ 权限护栏：跨用户数据隔离（基于已知 userId）
    scope_scan = check_scope(reply_text, user_id)
    if scope_scan.flagged:
        metrics.inc("guardrail_scope_flagged")
        reply_text = scope_scan.sanitized

    # 6) 写缓存（存脱敏后的文本）
    cache.set(intent, text, reply_text, speech_rate)

    return {"reply_text": reply_text, "speech_rate": speech_rate,
            "tools": used_tools, "rag_hits": len(rag_hits),
            "ticket_id": ticket_id, "from_cache": False}
