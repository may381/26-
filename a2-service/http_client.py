# -*- coding: utf-8 -*-
"""
http_client.py —— 共享异步 HTTP 客户端（竞赛级：连接池 + 超时 + 统一出口）
==========================================================================
用 httpx.AsyncClient 替代标准库 urllib。urllib 是同步阻塞调用，在 FastAPI 异步框架里
会阻塞事件循环，属于教学演示级写法，不符合竞赛工程标准。
客户端在应用启动时创建、关闭时释放，复用连接池（max_connections / keepalive）。
"""
import httpx

from settings import settings

_client: httpx.AsyncClient | None = None


async def init_http_client() -> None:
    """应用启动时调用：创建带连接池与超时的异步客户端。"""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.LLM_TIMEOUT),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        )


async def close_http_client() -> None:
    """应用关闭时调用：释放连接。"""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def get_client() -> httpx.AsyncClient:
    """获取共享客户端；未初始化则惰性创建（便于测试）。"""
    if _client is None or _client.is_closed:
        await init_http_client()
    assert _client is not None
    return _client
