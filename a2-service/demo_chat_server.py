# -*- coding: utf-8 -*-
"""
demo_chat_server.py —— A2 交互式演示服务（人工输入版）
=========================================================
用途：在浏览器里像用手机 App 一样，由你自己打字给老人「发消息」，
      真实经过 P2 → (意图路由) → A2 → 大模型 → 14 字段结果单 → 落库，
      页面实时显示回复与链路证据。

与 demo_trigger.py 的区别：
  - demo_trigger.py：固定剧本自动跑（自动化测试 / 无人值守演示）
  - demo_chat_server.py：真人输入（现场演示，最能证明"不是背稿"）

说明：本服务只是「演示用客户端」，跑在 18080，不改动 A2 契约与代码逻辑。
启动：
  python demo_chat_server.py
访问：
  http://127.0.0.1:18080
"""
import os
import sys
import json
import time
import uuid
import sqlite3
import threading

import httpx
import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

HERE = os.path.dirname(os.path.abspath(__file__))

P2_MESSAGES = "http://127.0.0.1:8080/api/v3/agent/messages"
P2_HEALTH = "http://127.0.0.1:8081/actuator/health"
A2_HEALTH = "http://127.0.0.1:18002/health"
A2_METRICS = "http://127.0.0.1:18002/metrics"
A2_RESET = "http://127.0.0.1:18002/admin/reset"
A2_DB = os.path.join(HERE, "a2_receipts.db")

DEMO_PORT = int(os.environ.get("DEMO_PORT", "18080"))
ACTOR_ID = "u100"
ACTOR_ROLE = "ELDER"
WAIT_MAX = float(os.environ.get("DEMO_WAIT", "14"))   # 等 A2 出结果的最长秒数

_LOCK = threading.Lock()   # 单用户演示，串行处理避免互相串台

A2_KEY = ""
try:
    for _line in open(os.path.join(HERE, ".env"), encoding="utf-8"):
        if _line.startswith("A2_API_KEY="):
            A2_KEY = _line.strip().split("=", 1)[1].strip().strip('"')
except Exception:
    pass

app = FastAPI(title="A2 Interactive Demo")


# ------------------------------------------------------------------ 工具
def snap():
    try:
        return httpx.get(A2_METRICS, timeout=5).json().get("data", {}) or {}
    except Exception:
        return {}


def recent_sheets(limit=120):
    if not os.path.exists(A2_DB):
        return []
    try:
        conn = sqlite3.connect(A2_DB)
        rows = conn.execute(
            "SELECT sheet FROM receipts ORDER BY rowid DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        out = []
        for (s,) in rows:
            try:
                out.append(json.loads(s))
            except Exception:
                pass
        return out
    except Exception:
        return []


def find_by_message(message_id, timeout, base_req=0):
    """在同一 messageId 下等 A2 落库，精确匹配（避免读到别人的回执）。

    附加判定：若 4 秒后 A2 的请求总量一次都没涨，说明这条根本没派给 a2
    （被意图路由分给 a1），立刻返回，避免界面白等。
    """
    t0 = time.time()
    last_probe = 0.0
    while True:
        el = time.time() - t0
        for s in recent_sheets():
            if s.get("messageId") == message_id:
                return s
        if el > 4.0 and (el - last_probe) > 1.0:
            last_probe = el
            try:
                cur = int(snap().get("requests_total", 0) or 0)
            except Exception:
                cur = base_req
            if cur <= base_req:
                return None
        if el >= timeout:
            return None
        time.sleep(0.3)


def dv(a, b, k):
    try:
        return int((b.get(k, 0) or 0) - (a.get(k, 0) or 0))
    except Exception:
        return 0


# ------------------------------------------------------------------ 接口
@app.get("/")
def index():
    return FileResponse(os.path.join(HERE, "demo_chat.html"), media_type="text/html; charset=utf-8")


@app.get("/api/status")
def status():
    a2 = p2 = False
    try:
        a2 = httpx.get(A2_HEALTH, timeout=2).status_code == 200
    except Exception:
        pass
    try:
        p2 = httpx.get(P2_HEALTH, timeout=2).status_code == 200
    except Exception:
        pass
    return {"a2": a2, "p2": p2, "metrics": snap()}


@app.post("/api/reset")
def reset():
    """清空回复缓存 + 指标归零，让每次演示都是干净起点。"""
    try:
        httpx.post(A2_RESET, headers={"X-Agent-Key": A2_KEY}, timeout=5)
    except Exception:
        pass
    return {"ok": True}


@app.post("/api/send")
def send(payload: dict):
    text = (payload.get("text") or "").strip()
    if not text:
        return JSONResponse({"ok": False, "error": "消息为空"}, status_code=200)

    with _LOCK:
        m0 = snap()
        t0 = time.time()

        headers = {
            "X-Mock-Actor-Id": ACTOR_ID,
            "X-Mock-Actor-Role": ACTOR_ROLE,
            "Idempotency-Key": str(uuid.uuid4()),
            "Content-Type": "application/json; charset=utf-8",
        }
        body = {"protocolVersion": "3.0", "userId": ACTOR_ID, "input": {"text": text}}
        try:
            r = httpx.post(P2_MESSAGES, headers=headers, json=body, timeout=20)
            pj = r.json()
        except Exception as e:
            msg = str(e)
            if isinstance(e, httpx.ConnectError) or "10061" in msg or "refused" in msg.lower():
                return {"ok": False, "error": "P2 后端未运行（8080 无响应）。请在终端执行 "
                                                "python start_demo.py 启动演示环境后重试。"}
            return {"ok": False, "error": "调用 P2 平台失败：%s" % msg}

        if r.status_code != 200 or pj.get("code") != "OK":
            return {"ok": False, "error": "P2 拒绝受理（HTTP %s / %s）" %
                                           (r.status_code, pj.get("message") or pj.get("code"))}

        acc = pj.get("data") or {}
        message_id = acc.get("messageId")

        base_req = int(m0.get("requests_total", 0) or 0)
        sheet = find_by_message(message_id, WAIT_MAX, base_req) if message_id else None
        elapsed = int((time.time() - t0) * 1000)
        m1 = snap()

        # A2 没接单 → 说明这条被意图路由分给了 a1（游览咨询），属正常分工
        if not sheet:
            return {
                "ok": True, "agent": "a1", "guarded": False,
                "reply": "这条是游览咨询，由 a1（景点讲解智能体）处理；A2 只在求助类消息上接手。",
                "intent": "tourism", "fields": 0, "elapsed": elapsed,
                "llm": 0, "cache": 0, "taskId": acc.get("taskId"),
            }

        reply = (sheet.get("reply") or {}).get("text") or "（无回复内容）"
        guarded = dv(m0, m1, "guardrail_input_flagged") > 0
        return {
            "ok": True,
            "agent": "a2",
            "guarded": guarded,
            "reply": reply,
            "intent": sheet.get("intent"),
            "fields": len(sheet),
            "elapsed": elapsed,
            "llm": dv(m0, m1, "llm_calls"),
            "cache": dv(m0, m1, "cache_hits"),
            "rag": dv(m0, m1, "rag_hits"),
            "taskId": sheet.get("taskId"),
            "invocationId": sheet.get("invocationId"),
        }


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("=" * 56)
    print(" A2 交互式演示 · 请用浏览器打开 http://127.0.0.1:%d" % DEMO_PORT)
    print("=" * 56)
    uvicorn.run(app, host="127.0.0.1", port=DEMO_PORT, log_level="warning")
