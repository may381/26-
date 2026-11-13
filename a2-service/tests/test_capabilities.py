# -*- coding: utf-8 -*-
"""
test_capabilities.py —— 八项业务能力逐一审验（竞赛级交付锁）
==========================================================
覆盖《智能体三人分工》中 A2 的 8 大职责模块：
  求助与人工 / 健康提醒 / 记忆反馈 / 健康生活 / 家庭照护 / 家庭协同 / 社区活动 / 志愿服务
每项断言：返回合法 14 字段结果单 + 关键结构化字段（handoff/results/usedMemoryRefs）已填实 +
tools 为契约 4.2 对象数组。LLM/P2 用打桩，不依赖真实服务。
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agent_logic

# 打桩：避免依赖真实大模型 / P2
async def _fake_llm(text, context=None):
    return {"reply": "（测试）已为您处理：" + (text or "")[:10], "speechRate": 0.9}, None


async def _fake_p2(tool, args, token, trace_id):
    return {"result": {"entries": []}}, None


agent_logic.call_llm = _fake_llm
agent_logic.call_p2_tool = _fake_p2

from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402

KEY = "test-key-0000000000000000"

# (能力key, 派发 intent, 消息, 期望非空的结构化字段)
CAPS = [
    ("help_human",     "help",      "我在景区迷路了，急需帮助，请通知我的家人", "handoff"),
    ("health_reminder","health",    "提醒我每天上午9点吃降压药",            "results"),
    ("memory_feedback","memory",    "记住我不喜欢人多拥挤的地方",          "results"),
    ("health_life",    "health",    "我血压偏高平时要注意什么",            "results"),
    ("family_care",    "ability",   "我儿女不在身边怎么办",                "results"),
    ("family_coord",   "care",      "我想让家人知道我的路线",              "results"),
    ("community",      "community", "小区最近有什么老人活动",              "results"),
    ("volunteer",      "volunteer", "我想报名做志愿者",                    "results"),
]

EXPECTED = {"intent", "domains", "taskId", "baseTaskVersion", "invocationId",
            "conversationId", "messageId", "reply", "control", "confirmationIds",
            "tools", "usedMemoryRefs", "handoff", "results"}


def _post(intent, text, inv):
    payload = {
        "protocolVersion": "3.0", "userId": "u100", "conversationId": "c", "messageId": "m",
        "capabilityToken": "tok", "intent": intent, "input": {"text": text},
        "task": {"id": "t", "version": 1, "invocationId": inv},
    }
    with TestClient(main.app) as c:
        return c.post("/internal/v3/messages", json=payload, headers={"X-Agent-Key": KEY})


def test_each_capability_returns_14_fields_and_structured():
    for key, intent, text, expect_field in CAPS:
        r = _post(intent, text, "inv-" + key)
        assert r.status_code == 200, (key, r.status_code, r.text[:200])
        sheet = r.json()["data"]
        assert set(sheet.keys()) == EXPECTED, (key, EXPECTED ^ set(sheet.keys()))
        assert sheet.get(expect_field) not in (None, [], ""), (key, "field %s empty" % expect_field)
        # 契约 4.2：tools 为对象数组
        for t in sheet["tools"]:
            assert "tool" in t and "args" in t, (key, t)


def test_help_handoff_to_family_when_mentions_family():
    r = _post("help", "我在景区迷路了，急需帮助，请通知我的家人", "inv-hf")
    ho = r.json()["data"]["handoff"]
    assert ho and ho["to"] == "family", ho


def test_help_no_handoff_for_ordinary_question():
    r = _post("help", "请问洗手间在哪里", "inv-hn")
    assert r.json()["data"]["handoff"] is None


def test_placeholder_capabilities_return_placeholder_sheet():
    # c2 健康提醒 / c3 记忆反馈 已回归契约 4.1 占位口径：不落库、不调 memory.write
    r1 = _post("health", "提醒我每天上午9点吃降压药", "inv-rm")
    d1 = r1.json()["data"]
    assert d1["control"]["next"] == "COMPLETE"
    assert d1["control"]["outcome"] == "PARTIALLY_SUCCEEDED"
    assert any(t["tool"] == "knowledge.search" for t in d1["tools"]), "占位须带白名单内示例工具"
    assert not any(t["tool"] == "memory.write" for t in d1["tools"]), "占位不得越白名单调 memory.write"
    assert d1["handoff"] is None

    r2 = _post("memory", "记住我不喜欢人多拥挤的地方", "inv-mm")
    d2 = r2.json()["data"]
    assert d2["control"]["next"] == "COMPLETE"
    assert d2["control"]["outcome"] == "PARTIALLY_SUCCEEDED"
    assert not any(t["tool"] == "memory.write" for t in d2["tools"])
    assert d2["usedMemoryRefs"] in (None, []), "占位不写真实记忆引用"


def test_placeholder_no_fake_memory_write():
    # 占位能力不得伪造 memory.write 工具或真实记忆引用（F3/D5）
    for intent, text in [("health", "提醒我复查血压"), ("memory", "记住我怕吵")]:
        r = _post(intent, text, "inv-ph-%s" % intent)
        d = r.json()["data"]
        assert not any(t["tool"] == "memory.write" for t in d["tools"])
        assert all("memoryId" not in ref for ref in (d["usedMemoryRefs"] or []))
