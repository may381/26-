"""真实反诈链路：提交一条合成材料 → 轮询 → 存证据。

只打本机 8000（反诈后端）和本机 8095（统一入口），不碰真实个人信息。
产出：A1new/qa/fraud-live-<时间>.json
"""
import json
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:8000"
ENTRY = "http://127.0.0.1:8095"
QA = Path(__file__).resolve().parent.parent / "A1new" / "qa"

SAMPLE = ("【快递客服】您的包裹在运输中丢失，可双倍赔付。请添加QQ群8812345办理，"
          "先缴纳300元保证金，再把收到的短信验证码发给客服，逾期视为放弃。")


def post(url, body, headers=None, timeout=60):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=data, method="POST",
                      headers={"Content-Type": "application/json", **(headers or {})})
    with urlopen(request, timeout=timeout) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def get(url, timeout=30):
    with urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def main():
    record = {"startedAt": datetime.now().isoformat(timespec="seconds"),
              "sample": SAMPLE, "steps": []}

    key = "live-" + uuid.uuid4().hex
    try:
        status, accepted = post(BASE + "/api/analyses",
                                {"text": SAMPLE, "username": "本地比赛演示"},
                                {"Idempotency-Key": key})
    except (HTTPError, URLError) as error:
        print("提交失败:", error)
        return 1
    identity = accepted.get("analysis_id")
    record["submit"] = {"http": status, "idempotencyKey": key, "response": accepted}
    print("提交 HTTP", status, "任务:", identity)

    if not isinstance(identity, str):
        print("没拿到任务号，停止")
        return 1

    deadline = time.monotonic() + 300
    last = None
    while time.monotonic() < deadline:
        try:
            state = get(BASE + "/api/analyses/" + identity)
        except (HTTPError, URLError) as error:
            print("查询失败:", error)
            time.sleep(3)
            continue
        status_text = state.get("status")
        if status_text != last:
            print("[%s] 状态: %s" % (datetime.now().strftime("%H:%M:%S"), status_text))
            record["steps"].append({"at": datetime.now().isoformat(timespec="seconds"),
                                    "status": status_text})
            last = status_text
        if status_text in ("completed", "failed", "interrupted"):
            record["final"] = state
            break
        time.sleep(3)
    else:
        record["final"] = {"status": "timeout", "note": "5 分钟内未完成"}
        print("超时，未完成")

    # 再过一遍统一入口，确认 8095 → 8000 的链路也通
    try:
        status, packet = post(ENTRY + "/api/message",
                              {"topic": "fraud", "text": SAMPLE}, timeout=120)
        record["entry"] = {"http": status, "packet": packet}
        print("统一入口 HTTP", status, "trace 段数:", len(packet.get("executionTrace", [])))
    except (HTTPError, URLError) as error:
        record["entry"] = {"error": str(error)}
        print("统一入口失败:", error)

    QA.mkdir(parents=True, exist_ok=True)
    out = QA / ("fraud-live-%s.json" % datetime.now().strftime("%Y%m%d-%H%M%S"))
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print("证据已保存:", out)

    final = record.get("final") or {}
    if final.get("status") == "completed":
        result = final.get("result") or {}
        print("风险:", result.get("risk_level"), "/", result.get("assessment"),
              "| 类型:", result.get("fraud_type"),
              "| 证据条数:", len(result.get("evidence_ids") or []))
    return 0


if __name__ == "__main__":
    sys.exit(main())
