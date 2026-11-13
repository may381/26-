# -*- coding: utf-8 -*-
"""
main.py —— A2 服务 HTTP 入口（FastAPI，异步；竞赛级工程结构）
============================================================
职责边界：只做路由分发、鉴权、请求校验、调业务层、统一返回信封。
业务推理 / LLM 调用 / P2 工具调用 / 回执持久化 拆到对应模块。

路由（严格对齐《Agent 统一交互协议 v3.0》）：
  GET  /health                             健康检查
  POST /internal/v3/messages               接收 P2 派活，返回模板 D 结果单
  GET  /internal/v3/invocations/{id}        按 invocationId 找回执
  POST /internal/v3/invocations/{id}/cancel 取消某个 invocation

统一响应信封：{"code": "...", "message": "...", "data": ...}
"""
import hmac
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from settings import settings
from http_client import init_http_client, close_http_client
from store import init_db, save_receipt, get_receipt, mark_cancelled, is_cancelled
from agent_logic import build_reply
from metrics import metrics
from cache import cache

logger = logging.getLogger("a2")
settings.require_key()
settings.setup_logging()


def envelope(code: str, message: str, data=None):
    return {"code": code, "message": message, "data": data}


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    await init_http_client()
    logger.info("A2 服务启动：LLM=%s/%s", settings.LLM_BASE_URL, settings.LLM_MODEL)
    try:
        yield
    finally:
        await close_http_client()
        logger.info("A2 服务已关闭")


app = FastAPI(title="A2 Agent v3", version="3.0", lifespan=lifespan)


def _auth_ok(x_agent_key: Optional[str]) -> bool:
    if not x_agent_key:
        return False
    return hmac.compare_digest(x_agent_key, settings.A2_API_KEY)


def _resolve_invocation_id(message: dict, x_trace_id: Optional[str]) -> str:
    """回执 key：优先 X-Trace-Id 头（即 invocationId），其次 task.invocationId。"""
    return (x_trace_id
            or (message.get("task") or {}).get("invocationId")
            or message.get("traceId", ""))


@app.get("/health")
async def health():
    return envelope("OK", "成功", {"agentId": "a2", "mode": "SERVICE"})


@app.get("/metrics")
async def metrics_endpoint():
    """⑧ 可观测性：暴露累计指标快照（可对接 Prometheus/ELK）。"""
    return envelope("OK", "成功", metrics.snapshot())


@app.post("/admin/reset")
async def admin_reset(x_agent_key: Optional[str] = Header(None)):
    """运维/演示用：清空回复缓存并重置指标计数（需 X-Agent-Key）。"""
    if not _auth_ok(x_agent_key):
        logger.warning("admin/reset 鉴权失败")
        return JSONResponse(status_code=401, content=envelope("UNAUTHORIZED", "X-Agent-Key 无效"))
    cache.clear()
    metrics.reset()
    logger.info("admin reset: cache cleared, metrics reset")
    return envelope("OK", "已清空缓存并重置指标",
                    {"cache": "cleared", "metrics": "reset"})


@app.post("/internal/v3/messages")
async def receive_dispatch(request: Request, x_agent_key: Optional[str] = Header(None)):
    if not _auth_ok(x_agent_key):
        logger.warning("派活请求鉴权失败")
        return JSONResponse(status_code=401, content=envelope("UNAUTHORIZED", "X-Agent-Key 无效"))

    try:
        message = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content=envelope("INVALID_ARGUMENT", "JSON 解析失败"))

    if not isinstance(message, dict):
        return JSONResponse(status_code=400, content=envelope("INVALID_ARGUMENT", "JSON 必须是对象"))

    if message.get("protocolVersion") != "3.0":
        return JSONResponse(status_code=400, content=envelope("UNSUPPORTED_PROTOCOL_VERSION", "协议版本必须是 3.0"))

    # 必填字段校验（字段名必须与 P2 派活请求一致）
    if not isinstance(message.get("input"), dict) or "text" not in message["input"]:
        return JSONResponse(status_code=400, content=envelope("INVALID_ARGUMENT", "缺少 input.text"))
    if not isinstance(message.get("userId"), str) or not message["userId"].strip():
        return JSONResponse(status_code=400, content=envelope("INVALID_ARGUMENT", "缺少 userId"))
    if not isinstance(message.get("capabilityToken"), str) or not message["capabilityToken"]:
        return JSONResponse(status_code=400, content=envelope("INVALID_ARGUMENT", "缺少 capabilityToken"))

    inv = _resolve_invocation_id(message, request.headers.get("X-Trace-Id"))
    if inv and is_cancelled(inv):
        return JSONResponse(status_code=409, content=envelope("CONFLICT", "该任务已取消"))

    # 异步业务推理（LLM / 工具调用均不阻塞事件循环）
    import time
    t0 = time.perf_counter()
    sheet = await build_reply(message)
    elapsed = (time.perf_counter() - t0) * 1000.0
    metrics.add_latency(elapsed)

    # 落盘持久化（sqlite），P2 超时后可按 invocationId 找回
    if inv:
        save_receipt(inv, sheet)

    # ⑧ 结构化留痕：每次派活输出指标快照，便于排障与容量评估
    logger.info("dispatch done intent=%s elapsed_ms=%.1f metrics=%s", settings.A2_INTENT, elapsed, metrics.snapshot())

    return JSONResponse(status_code=200, content=envelope("OK", "成功", sheet))


@app.get("/internal/v3/invocations/{invocation_id}")
async def get_receipt_endpoint(invocation_id: str):
    sheet = get_receipt(invocation_id)
    if sheet is None:
        return JSONResponse(status_code=404, content=envelope("NOT_FOUND", "回执不存在"))
    return JSONResponse(
        status_code=200,
        content={"invocationId": invocation_id, "status": "FINISHED",
                 "result": envelope("OK", "成功", sheet)},
    )


@app.post("/internal/v3/invocations/{invocation_id}/cancel")
async def cancel_endpoint(invocation_id: str):
    mark_cancelled(invocation_id)
    return JSONResponse(status_code=200, content=envelope("OK", "成功",
                                                          {"invocationId": invocation_id, "cancelled": True}))


if __name__ == "__main__":
    import uvicorn

    logger.info("A2 领域智能体 v3 启动 (FastAPI + httpx 异步，已接真实 LLM)")
    uvicorn.run(app, host=settings.LISTEN_HOST, port=settings.LISTEN_PORT, log_level="info")
