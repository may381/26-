"""端到端冒烟：一次跑完 A1 这条线的全部真实链路。

和单元测试的区别：
    单元测试证明"程序约束对"；这个脚本证明"服务真的连得上、结果真的回来了"。

覆盖 5 项：
    1. 入口存活 + 三端口状态
    2. 综合入口：缺城市 → ASK，且不派发
    3. 出行：咨询真的回到 8091
    4. 反诈：提交 → 轮询 → 拿到风险与原文证据
    5. 失败面：空输入 / 超长 / 非法 topic 都被挡住

用法：
    cd a1-orchestrator
    python -X utf8 e2e_smoke.py
全部通过时最后一行是 E2E OK；报告存到 A1new/qa/e2e-<时间>.json。
"""
import json
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.request import (HTTPCookieProcessor, Request, build_opener,
                            urlopen)

ENTRY = "http://127.0.0.1:8095"
# 会话靠 cookie 认人：整轮必须共用一个 cookie jar，否则每次都是新会话。
OPENER = build_opener(HTTPCookieProcessor(CookieJar()))
QA = Path(__file__).resolve().parent.parent / "A1new" / "qa"
FRAUD_SAMPLE = ("【快递客服】您的包裹在运输中丢失，可双倍赔付。请添加QQ群8812345办理，"
                "先缴纳300元保证金，再把收到的短信验证码发给客服，逾期视为放弃。")

results = []
report = {"startedAt": datetime.now().isoformat(timespec="seconds"), "checks": []}


def record(name, ok, detail=""):
    results.append(ok)
    report["checks"].append({"name": name, "ok": bool(ok), "detail": detail})
    print(("PASS  " if ok else "FAIL  ") + name + (("  ← " + detail) if detail else ""))


def post(path, body, timeout=180):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = Request(ENTRY + path, data=data, method="POST",
                      headers={"Content-Type": "application/json"})
    try:
        with OPENER.open(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8") or "{}")


def get(path, timeout=20):
    with urlopen(ENTRY + path, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def main():
    # 1. 存活与端口
    try:
        status = get("/api/system-status")
        ports = {c["name"]: c["reachable"] for c in status.get("checks", [])}
        record("入口存活，三端口状态可读", True,
               "、".join("%s=%s" % (k, "通" if v else "断") for k, v in ports.items()))
        report["ports"] = ports
    except (URLError, HTTPError, KeyError) as error:
        record("入口存活", False, str(error))
        return finish()

    # 2. 综合入口：缺城市必须追问，且不派发
    status, packet = post("/api/message", {"topic": "auto", "text": "我想出去玩，少走路"})
    trace = [t.get("stage") for t in packet.get("executionTrace", [])]
    ok = status == 200 and packet.get("domain") is None and "dispatch" not in trace
    record("缺城市 → 只追问、不派发", ok, "trace=%s" % trace)
    record("追问文案非空", bool((packet.get("reply") or "").strip()), (packet.get("reply") or "")[:30])

    # 3. 出行：真实打到 8091
    status, packet = post("/api/message", {"topic": "tourism", "text": "杭州两天怎么安排，少走路"})
    has_result = bool((packet.get("domainResult") or {}).get("text"))
    record("出行咨询返回真实内容", status == 200 and has_result,
           "domainResult 有 text" if has_result else str(packet)[:80])

    # 4. 反诈：提交 → 轮询
    status, packet = post("/api/message", {"topic": "fraud", "text": FRAUD_SAMPLE})
    accepted = (packet.get("domainResult") or {}).get("analysisId")
    record("反诈提交被受理", status == 200 and isinstance(accepted, str), str(accepted))

    final, waited = {}, 0
    while accepted and waited < 180:
        _, state = post("/api/message", {"topic": "auto", "text": "/status"})
        current = state.get("domainResult") or {}
        if current.get("status") in ("completed", "failed", "interrupted"):
            final = current
            break
        time.sleep(3)
        waited += 3
    result = final.get("result") or {}
    record("反诈任务完成", final.get("status") == "completed", "等待 %d 秒" % waited)
    record("返回风险等级与原文证据",
           bool(result.get("level")) and len(result.get("evidenceItems") or []) > 0,
           "level=%s 证据=%d 条" % (result.get("level"), len(result.get("evidenceItems") or [])))
    if result:
        report["fraudResult"] = {k: result.get(k) for k in
                                 ("id", "level", "type", "assessment", "model", "retrievalMethod")}
        report["fraudResult"]["evidenceCount"] = len(result.get("evidenceItems") or [])
        report["fraudResult"]["adviceCount"] = len(result.get("advice") or [])

    # 5. 失败面
    status, body = post("/api/message", {"topic": "auto", "text": ""})
    record("空输入被挡（4xx）", 400 <= status < 500, "HTTP %s" % status)
    status, body = post("/api/message", {"topic": "health", "text": "你好"})
    record("非法 topic 被挡（4xx）", 400 <= status < 500, "HTTP %s" % status)
    status, body = post("/api/message", {"topic": "auto", "text": "啊" * 3000})
    record("超长输入被挡（4xx）", 400 <= status < 500, "HTTP %s" % status)

    return finish()


def finish():
    passed = sum(1 for r in results if r)
    report["summary"] = {"passed": passed, "total": len(results),
                         "finishedAt": datetime.now().isoformat(timespec="seconds")}
    QA.mkdir(parents=True, exist_ok=True)
    out = QA / ("e2e-%s.json" % datetime.now().strftime("%Y%m%d-%H%M%S"))
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n%d/%d 项通过" % (passed, len(results)))
    print("报告：" + str(out))
    print("E2E OK" if passed == len(results) else "有失败项，见上面 FAIL")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
