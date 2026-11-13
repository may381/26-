"""接口自检：一次跑完「入站 8093」和「出站 p2_client」。

不依赖真实 P2、不依赖学校模型、不写业务库：
  - 入站：在进程内起一个 service.Handler，用假的 process 代替模型，
          验证鉴权 / 幂等（REPLAY、CONFLICT）/ 取消 / 错误码。
  - 出站：在进程内起一个「假 P2」，把 p2_client 真发出去的抓下来，
          验证路径、协议版本、幂等头、必填字段。

用法：
    cd a1-orchestrator
    python -X utf8 verify_interfaces.py
全部通过时最后一行是 ALL PASSED。
"""
import json
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import p2_client
import service

KEY = "k" * 32
results = []


def check(name, condition, detail=""):
    results.append(bool(condition))
    print(("PASS  " if condition else "FAIL  ") + name + (("  ← " + detail) if detail else ""))


def call(base, method, path, body=None, key=KEY, headers=None):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode()
    request = urllib.request.Request(base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json", **(headers or {})})
    if key:
        request.add_header("X-Agent-Key", key)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        raw = error.read().decode() or "{}"
        try:
            return error.code, json.loads(raw)
        except ValueError:
            return error.code, {"raw": raw}


def start(handler_cls):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, "http://127.0.0.1:%d" % server.server_port


def verify_inbound():
    print("\n=== 入站：P2 调 A1（8093 联调壳）===")
    receipts = service.Receipts(":memory:")
    stub = lambda body: {"code": "OK", "message": "stub", "data": {"ok": True}}
    server, base = start(service.make_handler(receipts, KEY, process=stub))
    try:
        status, body = call(base, "GET", "/health", key=None)
        check("健康检查不需要密钥", status == 200 and body["data"]["mode"] == "INTEGRATION_SHELL")

        status, body = call(base, "GET", "/internal/v3/invocations/any", key=None)
        check("无密钥查收据 → 401", status == 401 and body["code"] == "UNAUTHORIZED")

        status, body = call(base, "GET", "/internal/v3/invocations/any", key="wrong-key")
        check("错密钥 → 401", status == 401)

        status, body = call(base, "POST", "/internal/v3/messages", {})
        check("缺 invocationId → 400", status == 400 and body["code"] == "INVALID_ARGUMENT")

        task = {"invocationId": "inv-1", "goal": "查长沙课程"}
        status, body = call(base, "POST", "/internal/v3/messages", {"task": task})
        check("首次投递 → 200 并返回结果", status == 200 and body["data"] == {"ok": True})

        status, body = call(base, "POST", "/internal/v3/messages", {"task": task})
        check("同 ID 同内容重投 → 返回原结果（REPLAY）", status == 200 and body["data"] == {"ok": True})

        status, body = call(base, "POST", "/internal/v3/messages", {"task": {**task, "goal": "改过的目标"}})
        check("同 ID 改内容 → 409 CONFLICT", status == 409 and body["code"] == "CONFLICT")

        status, body = call(base, "GET", "/internal/v3/invocations/inv-1")
        check("收据可查，状态为 FINISHED", status == 200 and body["data"]["status"] == "FINISHED")

        cancel_body = {"protocolVersion": "3.0", "invocationId": "inv-1",
                       "cancelRequestId": "cancel-1", "reason": "用户取消"}
        status, body = call(base, "POST", "/internal/v3/invocations/inv-1/cancel", cancel_body)
        check("取消登记 → 200 并给状态", status == 200 and "status" in body["data"])

        status, body = call(base, "POST", "/internal/v3/invocations/inv-1/cancel", cancel_body)
        check("同 cancelRequestId 重放 → 返回同一份", status == 200 and body["data"]["cancelRequestId"] == "cancel-1")

        bad = {**cancel_body, "reason": "换了原因"}
        status, body = call(base, "POST", "/internal/v3/invocations/inv-1/cancel", bad)
        check("同 ID 不同内容 → 409", status == 409)

        status, body = call(base, "POST", "/internal/v3/messages", {"task": {"invocationId": "bad id!"}})
        check("非法 invocationId → 400", status == 400)
    finally:
        server.shutdown()
        server.server_close()


CAPTURED = []


class FakeP2(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        size = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(size).decode() or "{}")
        CAPTURED.append({"path": self.path, "headers": dict(self.headers), "body": body})
        raw = json.dumps({"code": "OK", "message": "ok", "data": {"stub": True}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def verify_outbound():
    print("\n=== 出站：A1 调 P2（p2_client）===")
    server, base = start(FakeP2)
    try:
        client = p2_client.P2Client(base=base, key=KEY, trace_id="trace-1",
                                    context_token="context-1")
        client.delegate("conv-1", "task-1", "act-1", {"goal": "查长沙剪纸课程"})
        client.register_steps("task-1", "req-key-1", 1, [{"stepId": "s1", "goal": "查课程"}])
        client.prepare_action("task-1", "s1", {"tool": "culture.search"}, idempotency_key="idem-1")
        client.prepare_confirmation("task-1", "act-1")
        client.execute_tool("task-1", "s1", "act-1", "route.recommend",
                            {"walkDurationMin": 40, "avoidSteps": True})

        paths = [c["path"] for c in CAPTURED]
        check("5 个出站路径都正确", paths == [
            "/internal/agent/v3/delegations",
            "/internal/agent/v3/tasks/task-1/steps",
            "/internal/agent/v3/actions",
            "/internal/agent/v3/confirmations",
            "/internal/agent/v3/tools",
        ], str(paths))

        check("协议版本固定 3.0", all(c["body"]["protocolVersion"] == "3.0" for c in CAPTURED))
        check("都带 X-Agent-Key", all(c["headers"].get("X-Agent-Key") == KEY for c in CAPTURED))
        check("都带 X-Trace-Id", all(c["headers"].get("X-Trace-Id") == "trace-1" for c in CAPTURED))
        check("动作准备带 Idempotency-Key", CAPTURED[2]["headers"].get("Idempotency-Key") == "idem-1")
        check("工具执行带 X-Agent-Context", CAPTURED[4]["headers"].get("X-Agent-Context") == "context-1")
        check("委派字段与 schema 一致",
              set(CAPTURED[0]["body"]) == {"protocolVersion", "conversationId", "taskId", "actionId", "input"})
        check("步骤登记带 requestKey/planVersion",
              CAPTURED[1]["body"]["requestKey"] == "req-key-1" and CAPTURED[1]["body"]["planVersion"] == 1)

        print("\n  —— 实际发出去的委派报文 ——")
        print("  " + json.dumps(CAPTURED[0]["body"], ensure_ascii=False))

        try:
            p2_client.P2Client(base=base, key=None).delegate("c", "t", "a", {})
            check("没配密钥时拒绝发送", False, "居然发出去了")
        except p2_client.P2Error as error:
            check("没配密钥时拒绝发送", "A1_AGENT_KEY" in str(error))

        try:
            client.prepare_action("task-1", "s1", {}, idempotency_key="")
            check("动作缺幂等键时拒绝", False, "居然发出去了")
        except p2_client.P2Error:
            check("动作缺幂等键时拒绝", True)
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    verify_inbound()
    verify_outbound()
    passed = sum(results)
    print("\n%d/%d 项通过" % (passed, len(results)))
    print("ALL PASSED" if passed == len(results) else "有失败项，逐条看上面的 FAIL")
