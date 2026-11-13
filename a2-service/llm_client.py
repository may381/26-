# -*- coding: utf-8 -*-
"""
llm_client.py —— 封装对统一大模型（校内 qwen）的异步调用
=========================================================
依据《智能体三人分工与调用关系》第 3 节「学校模型怎么调用」：
  模型：qwen3.8-27b
  地址：http://10.138.50.151:8000/v1/chat/completions（OpenAI 兼容，校内免 Key）
  回复取 choices[0].message.content

竞赛级实现：httpx 异步客户端（连接池 + 超时 + 异常细分），不再用标准库 urllib 同步阻塞。
返回：( {"reply": str, "speechRate": float}, None ) 成功；或 ( None, 错误说明 ) 失败。
"""
import asyncio
import json
import logging
from typing import Optional, Tuple

import httpx

from settings import settings
from http_client import get_client

logger = logging.getLogger("a2.llm")


def _parse_content(content: str, fallback_text: str) -> Tuple[Optional[dict], Optional[str]]:
    try:
        parsed = json.loads(content)
    except Exception:
        return None, "LLM 返回非 JSON"
    reply = parsed.get("reply") or fallback_text or "已收到您的诉求。"
    try:
        sr = float(parsed.get("speechRate", 0.8))
    except (TypeError, ValueError):
        sr = 0.8
    if not (0.5 <= sr <= 1.5):
        sr = 0.8
    return {"reply": reply, "speechRate": sr}, None


async def call_llm(text: str, context: Optional[str] = None) -> Tuple[Optional[dict], Optional[str]]:
    if not settings.LLM_ENABLED:
        return None, "LLM 已通过 A2_LLM_ENABLED 关闭"
    if not settings.LLM_BASE_URL:
        return None, "未配置 LLM_BASE_URL"

    from prompts import SYSTEM_PROMPT  # 延迟导入，避免循环依赖

    user_content = "用户输入：%s" % (text or "")
    # ③ RAG：把本地知识检索结果作为参考上下文注入（仅用于生成，不对外复述内部标识）
    if context:
        user_content += "\n\n【参考知识（仅用于生成回复，不要原样复述内部编号或系统标识）】\n%s" % context

    body = {
        "model": settings.LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.3,
        "max_completion_tokens": 1024,
        "stream": False,
        "response_format": {"type": "json_object"},
        "chat_template_kwargs": {"enable_thinking": False},
    }
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if settings.LLM_API_KEY:
        headers["Authorization"] = "Bearer %s" % settings.LLM_API_KEY

    url = settings.LLM_BASE_URL.rstrip("/") + "/v1/chat/completions"
    # ⑦ 模型路由：主模型 -> 备用模型（主模型彻底失败后再切，避免无效抖动）
    models = [m for m in [settings.LLM_MODEL, settings.LLM_MODEL_SECONDARY] if m]
    # 竞赛级韧性：外部大模型是抖动依赖，网络瞬时错误重试，4xx 不重试。
    attempts = max(1, int(settings.LLM_MAX_RETRIES))
    last_err: Optional[str] = None
    for model in models:
        body["model"] = model
        for attempt in range(1, attempts + 1):
            try:
                client = await get_client()
                resp = await client.post(url, json=body, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return _parse_content(content, text)
            except httpx.HTTPStatusError as e:
                # 4xx 多为请求格式/鉴权问题，重试无意义；仅 5xx 视为可重试。
                status = e.response.status_code
                if 500 <= status <= 599:
                    last_err = "LLM HTTP %d" % status
                    logger.warning("LLM[%s] 返回 %d，第 %d/%d 次可重试", model, status, attempt, attempts)
                else:
                    return None, "LLM HTTP %d" % status
            except httpx.RequestError as e:
                last_err = "LLM 请求失败: %s" % e
                logger.warning("LLM[%s] 网络错误（%s），第 %d/%d 次重试", model, type(e).__name__, attempt, attempts)
            except Exception as e:  # 返回格式异常等兜底，不重试
                return None, "LLM 调用失败: %s" % e
            if attempt < attempts:
                await asyncio.sleep(settings.LLM_RETRY_BACKOFF)
        logger.warning("LLM 主模型 %s 在 %d 次尝试后失败，尝试备用模型", model, attempts)
    logger.error("LLM 调用在所有模型尝试后仍失败：%s", last_err)
    return None, last_err or "LLM 调用失败"
