# -*- coding: utf-8 -*-
"""A2 服务集成测试：用 FastAPI TestClient 驱动，mock 掉外部 LLM / P2 依赖。"""
from fastapi.testclient import TestClient

import agent_logic
import main

API_KEY = "test-key-0000000000000000"


async def fake_llm(text, context=None):
    return {"reply": "（测试回复）" + (text or ""), "speechRate": 0.9}, None


async def fake_p2_tool(tool, args, token, trace_id):
    return {"result": {"entries": [{"title": "无障碍通道"}]}}, None


# 替换外部依赖，保证测试不依赖真实 LLM / P2
agent_logic.call_llm = fake_llm
agent_logic.call_p2_tool = fake_p2_tool


def _sample_dispatch(inv="inv-unit-1"):
    return {
        "protocolVersion": "3.0",
        "userId": "u100",
        "conversationId": "c1",
        "messageId": "m1",
        "capabilityToken": "tok",
        "input": {"text": "景区有电梯吗"},
        "task": {"id": "t1", "version": 1, "invocationId": inv},
    }


def test_health():
    with TestClient(main.app) as client:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["code"] == "OK"


def test_messages_ok_14_fields():
    with TestClient(main.app) as client:
        r = client.post("/internal/v3/messages", json=_sample_dispatch(),
                        headers={"X-Agent-Key": API_KEY})
        assert r.status_code == 200
        data = r.json()["data"]
        assert len(data) == 14, data.keys()
        assert data["invocationId"] == "inv-unit-1"
        assert data["taskId"] == "t1"
        assert data["reply"]["text"].startswith("（测试回复）")


def test_messages_auth_fail():
    with TestClient(main.app) as client:
        r = client.post("/internal/v3/messages", json=_sample_dispatch(),
                        headers={"X-Agent-Key": "wrong"})
        assert r.status_code == 401


def test_messages_missing_fields():
    with TestClient(main.app) as client:
        r = client.post("/internal/v3/messages", json={"protocolVersion": "3.0"},
                        headers={"X-Agent-Key": API_KEY})
        assert r.status_code == 400


def test_protocol_version_wrong_code():
    # 验收 A5：协议版本非 3.0 必须返回 UNSUPPORTED_PROTOCOL_VERSION（非 INVALID_ARGUMENT）
    with TestClient(main.app) as client:
        r = client.post("/internal/v3/messages", json={
            "protocolVersion": "2.0", "userId": "u100", "conversationId": "c",
            "messageId": "m", "capabilityToken": "tok", "input": {"text": "x"}},
            headers={"X-Agent-Key": API_KEY})
        assert r.status_code == 400
        assert r.json()["code"] == "UNSUPPORTED_PROTOCOL_VERSION"


def test_receipt_roundtrip_and_cancel():
    with TestClient(main.app) as client:
        # 先派活生成回执
        client.post("/internal/v3/messages", json=_sample_dispatch("inv-rt-1"),
                    headers={"X-Agent-Key": API_KEY})
        # 按 invocationId 找回
        r = client.get("/internal/v3/invocations/inv-rt-1")
        assert r.status_code == 200
        assert r.json()["result"]["data"]["invocationId"] == "inv-rt-1"
        # 取消
        c = client.post("/internal/v3/invocations/inv-rt-1/cancel")
        assert c.status_code == 200
        # 取消后再次派活应命中已取消
        r2 = client.post("/internal/v3/messages", json=_sample_dispatch("inv-rt-1"),
                         headers={"X-Agent-Key": API_KEY})
        assert r2.status_code == 409


def test_receipt_missing():
    with TestClient(main.app) as client:
        r = client.get("/internal/v3/invocations/not-exist")
        assert r.status_code == 404
