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
        ("fraud", ("诈骗", "转账")), ("health", ("健康", "饮食")),
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

    def do_POST(self):
        keys = self.headers.get_all("X-Agent-Key", [])
        if len(keys) != 1 or not hmac.compare_digest(keys[0], self.server.api_key):
            self.respond(401)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 16384:
                self.respond(400)
                return
            self.error_code = "INVALID_ARGUMENT"
            message = json.loads(self.rfile.read(length))
            del self.error_code
            if not isinstance(message, dict):
                self.respond(400, message="JSON body must be an object")
                return
            if message.get("protocolVersion") != "3.0":
                self.error_code = "UNSUPPORTED_PROTOCOL_VERSION"
                self.respond(400, message="Unsupported protocol version")
                return
            allowed = {"protocolVersion", "input"} if self.path == "/internal/v3/intents" else {"protocolVersion", "input", "userId", "intent", "context", "toolContextToken"}
            input_data = message.get("input")
            if set(message) - allowed or not isinstance(input_data, dict) or set(input_data) != {"text"}:
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
            if not isinstance(message.get("userId"), str) or not message["userId"].strip() or not isinstance(message.get("toolContextToken"), str):
                self.respond(400, message="Missing userId or toolContextToken")
                return
            expected_intent = {"a1": "tourism", "a2": "help"}.get(self.server.agent_id)
            if expected_intent and message.get("intent") != expected_intent:
                self.respond(400, message="Invalid intent for agent")
                return
            tools = []
            handoff = None
            if self.server.agent_id == "a1":
                call = self.tool(message, "knowledge.search", {"query": message["input"]["text"], "intent": "tourism"})
                tools.append(call)
                titles = [entry["title"] for entry in call["result"]["entries"]]
                text = "【Python mock】" + ("、".join(titles) if titles else call["result"]["message"])
                text += "；仅用于协议演示，不推测最近距离。"
            elif self.server.agent_id == "a2":
                location = (message.get("context") or {}).get("location")
                if location:
                    try:
                        tools.append(self.tool(message, "help.create", {"type": "GENERAL", "location": {"spotId": location},
                                                                     "locationNote": "Python mock 协议联调演示，非真实求助"}))
                    except HTTPError as error:
                        if error.code != 409:
                            raise
                text = ("【Python mock】求助已记录，通知仅为模拟。" if tools else
                        "【Python mock】请提供位置并使用带稳定请求 Key 的求助操作；尚未创建求助。")
                handoff = {"type": "human_handoff", "to": "scenic", "reason": "演示转人工请求，不代表已有人接单"}
            else:
                text = "【Python mock】A3 记忆协议尚未开放，不写入长期记忆。"
            self.respond(200, {"intent": message["intent"], "reply": {"text": text, "speechRate": 0.8,
                               "audioUrl": None}, "tools": tools, "handoff": handoff})
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
