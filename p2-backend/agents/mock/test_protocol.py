"""Run with: python -m unittest discover -s agents/mock -p test_protocol.py"""
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from server import Handler


class Callback(BaseHTTPRequestHandler):
    calls = []

    def log_message(self, *_):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.calls.append((body, dict(self.headers)))
        payload = json.dumps({"code": "OK", "message": "成功", "data": {
            "tool": body["input"]["tool"], "args": body["input"]["args"],
            "result": {"entries": [{"title": "演示设施"}]}
        }}).encode()
        self.send_response(200)
        self.end_headers()
        self.wfile.write(payload)


class ProtocolTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.callback = ThreadingHTTPServer(("127.0.0.1", 0), Callback)
        cls.agent = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.agent.agent_id = "a1"
        cls.agent.api_key = "test-only-agent-service-key"
        cls.agent.callback = f"http://127.0.0.1:{cls.callback.server_port}"
        for server in (cls.callback, cls.agent):
            threading.Thread(target=server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        for server in (cls.agent, cls.callback):
            server.shutdown()
            server.server_close()

    def call(self, path, body, key=None):
        request = Request(f"http://127.0.0.1:{self.agent.server_port}{path}",
                          data=json.dumps(body).encode(), headers={
                              "Content-Type": "application/json",
                              "X-Agent-Key": key or self.agent.api_key,
                              "X-Trace-Id": "test-trace"})
        try:
            response = urlopen(request, timeout=3)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.loads(response.read()), response.headers

    def test_classification_and_version_errors(self):
        status, body, headers = self.call("/internal/v3/intents", {
            "protocolVersion": "3.0", "input": {"text": "我要找人帮忙"}})
        self.assertEqual((status, body["data"]["intent"]), (200, "help"))
        self.assertEqual(headers["X-Agent-Protocol-Version"], "3.0")
        self.assertEqual(headers["X-Trace-Id"], "test-trace")
        status, body, _ = self.call("/internal/v3/intents", {"text": "旧格式"})
        self.assertEqual((status, body["code"]), (400, "UNSUPPORTED_PROTOCOL_VERSION"))

    def test_message_returns_current_v3_task_shape(self):
        status, body, _ = self.call("/internal/v3/messages", {
            "protocolVersion": "3.0", "userId": "u100",
            "conversationId": "conv-1", "messageId": "msg-1",
            "task": {"id": "task-1", "version": 2, "invocationId": "invoke-1"},
            "input": {"text": "厕所在哪", "attachmentIds": []}, "context": {},
            "capabilityToken": "test-token"})
        self.assertEqual(status, 200)
        data = body["data"]
        self.assertEqual((data["taskId"], data["baseTaskVersion"], data["invocationId"]),
                         ("task-1", 2, "invoke-1"))
        self.assertEqual(data["control"], {"next": "COMPLETE", "outcome": "SUCCEEDED",
                                           "dependencyTaskIds": [], "inputRequest": None})
        self.assertEqual(data["tools"], [])

    def test_mixed_fields_and_invalid_key_are_rejected(self):
        body = {"protocolVersion": "3.0", "input": {"text": "你好"}, "text": "旧字段"}
        status, result, _ = self.call("/internal/v3/intents", body)
        self.assertEqual((status, result["code"]), (400, "INVALID_ARGUMENT"))
        status, result, _ = self.call("/internal/v3/intents", body, "wrong-key")
        self.assertEqual((status, result["code"]), (401, "UNAUTHORIZED"))


if __name__ == "__main__":
    unittest.main()
