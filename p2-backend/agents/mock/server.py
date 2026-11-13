"""Loopback-only protocol fixture: three HTTP endpoints, no LLM and no database access."""
import hmac
import json
import os
from pathlib import Path
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def load_local_environment():
    path = Path(__file__).resolve().parents[2] / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            name, separator, value = line.partition("=")
            if separator and name in {"AGENT_A1_API_KEY", "AGENT_A2_API_KEY", "AGENT_A3_API_KEY"}:
                os.environ.setdefault(name, value)


def classify(text):
    for intent, words in [
        ("help", ("求助", "迷路", "不舒服", "帮忙", "找人")),
        ("fraud", ("诈骗", "转账", "退款", "验证码", "陌生链接", "安全账户", "汇款")),
        ("care", ("照护", "陪诊")), ("culture", ("非遗", "文化课")),
        ("volunteer", ("志愿",)), ("ability", ("技能", "教人")),
        ("community", ("社区", "活动")),
    ]:
        if any(word in text for word in words):
            return intent
    return "tourism"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # No dialogue, credentials or context tokens in access logs.

    def respond(self, status, data=None, message="Python mock"):
        if status >= 400:
            print(f"mock {self.server.agent_id} {self.command} {self.path} -> {status}: {message}", flush=True)
        payload = json.dumps({"code": "OK" if status == 200 else getattr(self, "error_code", {400: "INVALID_ARGUMENT", 401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND", 409: "CONFLICT", 502: "UPSTREAM_ERROR"}.get(status, "INTERNAL_ERROR")),
                              "message": message, "data": data}, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Agent-Protocol-Version", "3.0")
        self.send_header("X-Trace-Id", self.headers.get("X-Trace-Id", ""))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path == "/health":
            self.respond(200, {"agentId": self.server.agent_id, "mode": "MOCK"})
        else:
            self.respond(404)

    def tool(self, message, tool, args):
        body = json.dumps({"protocolVersion": "3.0", "input": {"tool": tool, "args": args}}).encode("utf-8")
        request = Request(self.server.callback + "/internal/agent/v3/tools", data=body, method="POST", headers={
            "Content-Type": "application/json", "X-Agent-Key": self.server.api_key,
            "X-Agent-Context": message["toolContextToken"], "X-Trace-Id": self.headers.get("X-Trace-Id", ""),
        })
        with urlopen(request, timeout=5) as response:
            result = json.loads(response.read(1024 * 1024))
        if result.get("code") != "OK":
            raise ValueError("Tool failed")
        return result["data"]

    def read_json_body(self, maximum=16384):
        """Read fixed-length or RFC 7230 chunked request bodies with a strict size cap."""
        transfer = self.headers.get("Transfer-Encoding", "").lower()
        if transfer == "chunked":
            body = bytearray()
            while True:
                line = self.rfile.readline(128)
                if not line:
                    raise ValueError("Incomplete chunked body")
                size = int(line.split(b";", 1)[0].strip(), 16)
                if size == 0:
                    while self.rfile.readline(8192) not in (b"\r\n", b"\n", b""):
                        pass
                    break
                if len(body) + size > maximum:
                    raise ValueError("Request body too large")
                body.extend(self.rfile.read(size))
                if self.rfile.read(2) != b"\r\n":
                    raise ValueError("Invalid chunk terminator")
            if not body:
                raise ValueError("Empty request body")
            return json.loads(body)
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length <= maximum:
            raise ValueError("Invalid request length")
        return json.loads(self.rfile.read(length))

    def do_POST(self):
        keys = self.headers.get_all("X-Agent-Key", [])
        if len(keys) != 1 or not hmac.compare_digest(keys[0], self.server.api_key):
            self.respond(401)
            return
        try:
            self.error_code = "INVALID_ARGUMENT"
            message = self.read_json_body()
            del self.error_code
            if not isinstance(message, dict):
                self.respond(400, message="JSON body must be an object")
                return
            if message.get("protocolVersion") != "3.0":
                self.error_code = "UNSUPPORTED_PROTOCOL_VERSION"
                self.respond(400, message="Unsupported protocol version")
                return
            allowed = {"protocolVersion", "input"} if self.path == "/internal/v3/intents" else {
                "protocolVersion", "input", "userId", "conversationId", "messageId",
                "task", "context", "capabilityToken"
            }
            input_data = message.get("input")
            if (set(message) - allowed or not isinstance(input_data, dict)
                    or "text" not in input_data or set(input_data) - {"text", "attachmentIds"}):
                self.respond(400, message="Unknown or missing fields")
                return
            text_input = input_data.get("text")
            if not isinstance(text_input, str) or not text_input.strip() or len(text_input) > 2000:
                self.respond(400, message="Invalid input.text")
                return
            if self.path == "/internal/v3/intents" and self.server.agent_id == "a1":
                self.respond(200, {"intent": classify(message["input"]["text"])})
                return
            if self.path != "/internal/v3/messages":
                self.respond(404)
                return
            task = message.get("task")
            if (not isinstance(message.get("userId"), str) or not message["userId"].strip()
                    or not isinstance(message.get("conversationId"), str)
                    or not isinstance(message.get("messageId"), str)
                    or not isinstance(message.get("capabilityToken"), str)
                    or not isinstance(task, dict)
                    or not all(key in task for key in ("id", "version", "invocationId"))):
                self.respond(400, message="Missing v3 task metadata")
                return
            intent = classify(text_input) if self.server.agent_id == "a1" else {
                "a2": "care", "a3": "culture"
            }.get(self.server.agent_id, "tourism")
            handoff = None
            if self.server.agent_id == "a1":
                text = "【联调演示】A1 已接收并完成任务：" + text_input
                if intent == "fraud":
                    text = "【联调演示】已识别为反诈核对请求，请勿转账或提供验证码；真实分析由 A1 服务接入后返回。"
                elif intent == "tourism":
                    text = "【联调演示】已识别为旅游请求；当前验证的是 P2 与 A1 的完整调用链。"
            elif self.server.agent_id == "a2":
                text = "【联调演示】A2 已接收照护任务；当前未创建真实求助单。"
                handoff = {"type": "human_handoff", "to": "scenic", "reason": "演示转人工请求，不代表已有人接单"}
            else:
                text = "【联调演示】A3 已接收文化或记忆任务；当前不写入长期记忆。"
            data = {
                "conversationId": message["conversationId"],
                "messageId": message["messageId"],
                "taskId": task["id"],
                "baseTaskVersion": task["version"],
                "invocationId": task["invocationId"],
                "intent": intent,
                "domains": [intent],
                "control": {"next": "COMPLETE", "outcome": "SUCCEEDED",
                            "dependencyTaskIds": [], "inputRequest": None},
                "reply": {"text": text, "speechRate": 0.8, "audioUrl": None},
                "results": [], "confirmationIds": [], "tools": [],
                "handoff": handoff, "usedMemoryRefs": []
            }
            self.respond(200, data)
        except (ValueError, TypeError, KeyError):
            self.respond(400, message="请求字段或JSON格式错误")
        except Exception:
            self.respond(502, message="Python mock 或平台回调失败；不自动重试")


def main():
    load_local_environment()
    callback = os.environ.get("AGENT_CALLBACK_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
    uri = urlsplit(callback)
    if uri.scheme != "http" or uri.hostname not in {"127.0.0.1", "localhost"} or uri.username or uri.query or uri.fragment or uri.path:
        raise SystemExit("Mock callback must be a loopback HTTP root URL")
    servers = []
    for agent_id, port in [("a1", 18001), ("a2", 18002), ("a3", 18003)]:
        key = os.environ.get(f"AGENT_{agent_id.upper()}_API_KEY", "")
        if len(key) < 16:
            raise SystemExit("Configure three independent AGENT_A*_API_KEY values in local .env")
        server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        server.agent_id, server.api_key, server.callback = agent_id, key, callback
        servers.append(server)
    print("Python MOCK agents listening on loopback ports 18001/18002/18003", flush=True)
    try:
        for server in servers:
            threading.Thread(target=server.serve_forever, daemon=True).start()
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
