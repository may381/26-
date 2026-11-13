# -*- coding: utf-8 -*-
"""
p2_client.py —— 封装 A2 调用 P2 内部工具（A2 -> P2，异步）
===========================================================
协议：A2 在需要时调用 P2 的 /internal/agent/v3/tools 走知识检索等能力。

竞赛级实现：httpx 异步客户端（取代标准库 urllib 同步阻塞）。
成功返回 (data, None)；失败返回 (None, 错误说明)。
注意：独立部署的 A2 走这条通道是直接 HTTP 调用，不经过 P2 的 invocation 动作账本，
因此本模块仅用于「内部取数以组织回复文本」，工具不可用时优雅降级，不暴露内部细节。
"""
from typing import Optional, Tuple

import httpx

from settings import settings
from http_client import get_client


async def call_p2_tool(tool: str, args: dict, token: str, trace_id: str) -> Tuple[Optional[dict], Optional[str]]:
    """调 P2 的 /internal/agent/v3/tools。成功返回 (data, None)；失败返回 (None, 错误说明)。"""
    body = {
        "protocolVersion": "3.0",
        "input": {"tool": tool, "args": args},
    }
    headers = {
        "Content-Type": "application/json",
        "X-Agent-Key": settings.A2_API_KEY,        # A2 自身身份
        "X-Agent-Context": token,                  # P2 派活下发的 capabilityToken，原样回传
        "X-Trace-Id": trace_id,
    }
    url = settings.P2_BASE_URL + "/internal/agent/v3/tools"
    try:
        client = await get_client()
        resp = await client.post(url, json=body, headers=headers, timeout=5.0)
        resp.raise_for_status()
        result = resp.json()
        if result.get("code") != "OK":
            return None, "P2 工具返回错误码: %s" % result.get("code")
        return result.get("data"), None
    except httpx.HTTPStatusError as e:
        return None, "P2 工具 HTTP %d" % e.response.status_code
    except httpx.RequestError as e:
        return None, "调用 P2 工具失败: %s" % e
    except Exception as e:
        return None, "调用 P2 工具异常: %s" % e
