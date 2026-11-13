# -*- coding: utf-8 -*-
"""
run_eval.py —— 改提示词必测的回归测评 harness（竞赛级第⑨项）
==========================================================
- 确定性测评（默认）：monkeypatch call_llm 为「贴合品牌规则的模拟回复」，
  验证管线不变量：14 字段格式、长度≤60、品牌关键词、注入抗性、拒答品牌化。
  不依赖实时大模型 → CI / 每次改提示词都能跑，阻断回归。
- 语义测评（--live）：直连真实 LLM 跑同样用例，模型不可达则跳过（不报错）。

用法：
  python tests/eval/run_eval.py            # 确定性测评
  python tests/eval/run_eval.py --live    # 额外跑真实 LLM 语义测评
"""
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

# 让脚本可直接运行（不依赖 pytest 收集路径）
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_logic import build_reply  # noqa: E402
from guardrails import scan_input  # noqa: E402

CASES_PATH = Path(__file__).resolve().parent / "cases.json"
EXPECTED_KEYS = {
    "intent", "domains", "taskId", "baseTaskVersion", "invocationId",
    "conversationId", "messageId", "reply", "control", "confirmationIds",
    "tools", "usedMemoryRefs", "handoff", "results",
}


async def _stub_llm(text: str, context: str = None):
    """模拟一个「品牌合规」的 LLM 回复，用于确定性管线测评（async 以匹配 await 调用）。"""
    if any(k in text for k in ("痛", "紧急", "救命", "喘", "晕")):
        return {"reply": "请立即联系景区医疗点或拨打120，原地休息等待救援。", "speechRate": 0.8}, None
    if any(k in text for k in ("休息", "累", "歇")):
        return {"reply": "前面有休息区，我陪您慢慢过去歇会儿。", "speechRate": 0.8}, None
    if any(k in text for k in ("路", "厕所", "卫生间", "出口")):
        return {"reply": "直走左转就到了，我带您过去。", "speechRate": 0.8}, None
    return {"reply": "好的，我帮您看看，稍等。", "speechRate": 0.8}, None


def _make_message(text: str) -> Dict[str, Any]:
    return {
        "protocolVersion": "3.0",
        "userId": "u100",
        "conversationId": "conv-eval",
        "messageId": "msg-eval",
        "input": {"text": text},
        "task": {"id": "task-eval", "version": 1, "invocationId": "inv-eval"},
        "capabilityToken": "tok-eval",
    }


async def run_all() -> Dict[str, Any]:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    import agent_logic as ag  # 延迟导入，便于 monkeypatch
    original = ag.call_llm
    ag.call_llm = _stub_llm  # 确定性：不依赖实时大模型
    passed: List[str] = []
    failed: List[Dict[str, Any]] = []
    try:
        for c in cases:
            exp = c.get("expect", {})
            detail = {"id": c["id"], "category": c["category"]}
            try:
                if exp.get("expect_input_flagged"):
                    assert scan_input(c["input"]).flagged, "输入护栏未检出注入"
                sheet = await ag.build_reply(_make_message(c["input"]))
                keys = set(sheet.keys())
                assert keys == EXPECTED_KEYS, "字段数不符: %s" % (EXPECTED_KEYS ^ keys)
                reply_text = sheet["reply"]["text"]
                if "max_len" in exp:
                    assert len(reply_text) <= exp["max_len"], "回复超长 %d>%d" % (len(reply_text), exp["max_len"])
                for kw in exp.get("must_contain", []):
                    assert kw in reply_text, "缺少关键词: %s" % kw
                for kw in exp.get("must_not_contain", []):
                    assert kw not in reply_text, "不应出现关键词: %s" % kw
                passed.append(c["id"])
            except AssertionError as e:
                detail["error"] = str(e)
                failed.append(detail)
            except Exception as e:  # noqa: BLE001
                detail["error"] = "异常: %s" % e
                failed.append(detail)
    finally:
        ag.call_llm = original
    return {"total": len(cases), "passed": passed, "failed": failed}


async def run_live() -> Dict[str, Any]:
    """真实 LLM 语义测评；不可达则跳过。"""
    import httpx

    from settings import settings

    try:
        httpx.get(settings.LLM_BASE_URL, timeout=3)
    except Exception:
        return {"skipped": True, "reason": "LLM 不可达"}
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    passed: List[Dict[str, Any]] = []
    failed: List[Dict[str, Any]] = []
    for c in cases:
        exp = c.get("expect", {})
        sheet = await build_reply(_make_message(c["input"]))
        reply_text = sheet["reply"]["text"]
        ok = True
        err = ""
        if "max_len" in exp and len(reply_text) > exp["max_len"]:
            ok, err = False, "超长"
        for kw in exp.get("must_not_contain", []):
            if kw in reply_text:
                ok, err = False, "出现%s" % kw
        (passed if ok else failed).append({"id": c["id"], "reply": reply_text, "error": err})
    return {"skipped": False, "passed": passed, "failed": failed}


if __name__ == "__main__":
    res = asyncio.run(run_all())
    print("=== 确定性测评 ===")
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if res["failed"]:
        sys.exit(1)
    if "--live" in sys.argv:
        live = asyncio.run(run_live())
        print("=== 真实 LLM 语义测评 ===")
        print(json.dumps(live, ensure_ascii=False, indent=2))
