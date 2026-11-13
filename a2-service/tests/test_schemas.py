# -*- coding: utf-8 -*-
"""模板 D 结果单结构严格校验（与 P2 responseChecks.validate 的「恰好 14 字段」对齐）。"""
from schemas import build_result_sheet

EXPECTED_14 = {
    "intent", "domains", "taskId", "baseTaskVersion", "invocationId",
    "conversationId", "messageId", "reply", "control", "results",
    "confirmationIds", "tools", "handoff", "usedMemoryRefs",
}


def test_result_sheet_has_exactly_14_fields():
    sheet = build_result_sheet(
        meta={"taskId": "t1", "baseTaskVersion": 1, "invocationId": "i1",
              "conversationId": "c1", "messageId": "m1"},
        reply_text="测试回复", speech_rate=0.9,
    )
    assert set(sheet.keys()) == EXPECTED_14, sheet.keys()
    assert len(sheet) == 14


def test_meta_roundtrip():
    meta = {"taskId": "t-X", "baseTaskVersion": 3, "invocationId": "i-X",
            "conversationId": "c-X", "messageId": "m-X"}
    sheet = build_result_sheet(meta=meta, reply_text="x", speech_rate=0.8)
    assert sheet["taskId"] == "t-X"
    assert sheet["baseTaskVersion"] == 3
    assert sheet["invocationId"] == "i-X"
    assert sheet["conversationId"] == "c-X"
    assert sheet["messageId"] == "m-X"


def test_tools_declared():
    from schemas import build_tool
    meta = {"invocationId": "i1"}
    sheet = build_result_sheet(meta=meta, reply_text="x",
                               tools=[build_tool("knowledge.search", {"query": "x"}, {"items": []})])
    assert sheet["tools"] == [{"tool": "knowledge.search", "args": {"query": "x"}, "result": {"items": []}}]


def test_build_helpers_shape():
    from schemas import build_handoff, build_memory_ref, build_result_item
    ho = build_handoff("scenic", "老人请求现场帮助")
    assert ho == {"type": "human_handoff", "to": "scenic", "reason": "老人请求现场帮助"}
    mr = build_memory_ref("M001", "preference", "偏好少台阶路线")
    assert mr["memoryId"] == "M001" and mr["type"] == "preference"
    ri = build_result_item("建议", "原地休息", status="SUGGESTED", note="等待工作人员")
    assert ri["label"] == "建议" and ri["status"] == "SUGGESTED" and ri["note"] == "等待工作人员"


def test_reply_block_shape():
    sheet = build_result_sheet(meta={"invocationId": "i1"}, reply_text="你好", speech_rate=1.0)
    assert sheet["reply"]["text"] == "你好"
    assert sheet["reply"]["speechRate"] == 1.0
    assert sheet["reply"]["audioUrl"] is None
    assert sheet["control"]["next"] == "COMPLETE"
    assert sheet["control"]["outcome"] == "SUCCEEDED"
