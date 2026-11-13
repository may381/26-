import tempfile
import unittest
import json
import socket
import threading
import http.client
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest.mock import Mock
from pathlib import Path
from service import Receipts, make_handler
from service import load_service_key
from unittest.mock import patch
import os


class KeyTests(unittest.TestCase):
    def test_private_file_survives_new_shell(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            path = Path(directory) / ".a1-service-key"
            path.write_text("a" * 64, encoding="ascii")
            os.chmod(path, 0o600)
            self.assertEqual(load_service_key(path), "a" * 64)
            with patch.dict(os.environ, {"A1_SERVICE_KEY": "b" * 32}):
                self.assertEqual(load_service_key(path), "b" * 32)

    def test_missing_or_malformed_key_never_starts(self):
        with patch.dict(os.environ, {"A1_SERVICE_KEY": "short"}, clear=True):
            with self.assertRaises(SystemExit):
                load_service_key()


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.receipts = Receipts(":memory:")

    def test_duplicate_does_not_start_second_call(self):
        self.assertEqual(self.receipts.begin("i1", {"text": "test", "capabilityToken": "one"}), "NEW")
        self.assertEqual(self.receipts.begin("i1", {"text": "test", "capabilityToken": "two"}), "REPLAY")
        self.assertEqual(self.receipts.begin("i1", {"text": "changed"}), "CONFLICT")

    def test_finished_response_can_be_retrieved(self):
        self.receipts.begin("i1", {})
        result = {"code": "OK", "message": "test", "data": {"value": "test"}}
        self.assertTrue(self.receipts.finish("i1", result))
        self.assertEqual(self.receipts.get("i1")["result"], result)

    def test_cancel_discards_late_response(self):
        self.receipts.begin("i1", {})
        req = {"cancelRequestId": "c1", "reason": "test"}
        first = self.receipts.cancel("i1", req)
        self.assertEqual(first["status"], "CANCEL_REQUESTED")
        self.assertEqual(self.receipts.cancel("i1", req), first)
        self.assertFalse(self.receipts.finish("i1", {"code": "OK"}))
        self.assertEqual(self.receipts.get("i1")["status"], "CANCELLED")
        self.assertIsNone(self.receipts.get("i1")["result"])

    def test_cancel_id_collision_rejected(self):
        self.receipts.begin("i1", {})
        self.receipts.cancel("i1", {"cancelRequestId": "c1", "reason": "test"})
        with self.assertRaises(ValueError):
            self.receipts.cancel("i1", {"cancelRequestId": "c1", "reason": "changed"})

    def test_restart_preserves_finished_but_does_not_replay_running(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "receipt.sqlite3")
            store = Receipts(path)
            store.begin("running", {})
            store.begin("done", {})
            store.finish("done", {"code": "OK", "data": {}})
            store.db.close()
            restarted = Receipts(path)
            self.assertEqual(restarted.get("running")["status"], "FAILED")
            self.assertEqual(restarted.get("done")["status"], "FINISHED")
            restarted.db.close()


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.store = Receipts(":memory:")
        self.process = Mock(return_value={"code": "OK", "message": "MOCK", "data": {"testOnly": True}})
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.store, "test-key-only", self.process))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = "http://127.0.0.1:%s" % self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.store.db.close()

    def post(self, body, key="test-key-only"):
        request = Request(self.url + "/internal/v3/messages", data=json.dumps(body).encode(),
                          headers={"X-Agent-Key": key, "X-Trace-Id": "trace-test", "Content-Type": "application/json"})
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response), response.headers.get("X-Trace-Id")

    def chunked_post(self, body, key="test-key-only", chunk_size=7):
        """RFC 7230 chunked upload, the way P2's HTTP client may send it."""
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        chunks = (raw[offset:offset + chunk_size] for offset in range(0, len(raw), chunk_size))
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=5)
        try:
            connection.request("POST", "/internal/v3/messages", body=chunks,
                               headers={"X-Agent-Key": key, "Content-Type": "application/json"},
                               encode_chunked=True)
            response = connection.getresponse()
            return response.status, json.loads(response.read() or b"{}")
        finally:
            connection.close()

    def raw_chunked_post(self, wire_body):
        """Send a hand-written chunked body so malformed framing can be exercised."""
        head = (
            "POST /internal/v3/messages HTTP/1.1\r\n"
            "Host: 127.0.0.1\r\n"
            "X-Agent-Key: test-key-only\r\n"
            "Content-Type: application/json\r\n"
            "Transfer-Encoding: chunked\r\n\r\n"
        ).encode("ascii")
        with socket.create_connection(("127.0.0.1", self.server.server_address[1]), timeout=5) as sock:
            sock.sendall(head + wire_body)
            received = b""
            while True:
                part = sock.recv(4096)
                if not part:
                    break
                received += part
        status = int(received.split(b" ", 2)[1])
        body = json.loads(received.split(b"\r\n\r\n", 1)[1])
        return status, body

    def test_chunked_request_body_is_accepted(self):
        status, body = self.chunked_post({"task": {"invocationId": "i-chunked"}})
        self.assertEqual(status, 200)
        self.assertEqual(body["code"], "OK")
        self.assertEqual(self.process.call_count, 1)
        self.assertEqual(self.store.get("i-chunked")["status"], "FINISHED")

    def test_chunked_request_body_accepts_multibyte_utf8_split_across_chunks(self):
        status, body = self.chunked_post({"task": {"invocationId": "i-chunked-utf8"},
                                          "note": "反诈提醒"}, chunk_size=3)
        self.assertEqual(status, 200)
        self.assertEqual(body["code"], "OK")

    def test_chunked_request_body_respects_size_limit(self):
        status, body = self.raw_chunked_post(b"200000\r\n")  # declares 2 MiB, above the 1 MiB cap
        self.assertEqual(status, 400)
        self.assertEqual(body["code"], "INVALID_ARGUMENT")
        self.assertEqual(self.process.call_count, 0)

    def test_malformed_chunk_framing_is_rejected(self):
        status, body = self.raw_chunked_post(b"ZZZ\r\n")
        self.assertEqual(status, 400)
        self.assertEqual(body["code"], "INVALID_ARGUMENT")
        self.assertEqual(self.process.call_count, 0)

    def test_empty_chunked_body_is_rejected(self):
        status, body = self.raw_chunked_post(b"0\r\n\r\n")
        self.assertEqual(status, 400)
        self.assertEqual(body["code"], "INVALID_ARGUMENT")
        self.assertEqual(self.process.call_count, 0)

    def test_health_is_public_and_reports_v3_runtime_without_secrets(self):
        with urlopen(self.url + "/health", timeout=5) as response:
            body = json.load(response)
        self.assertEqual(body["code"], "OK")
        self.assertEqual(body["data"]["protocolVersion"], "3.0")
        self.assertTrue(body["data"]["inboundReady"])
        self.assertIsInstance(body["data"]["langGraphVersion"], str)
        self.assertNotIn("serviceKey", body["data"])

    def test_auth_and_duplicate_over_real_local_http(self):
        body = {"task": {"invocationId": "i-http"}}
        self.assertEqual(self.post(body, "wrong")[0], 401)
        self.assertEqual(self.process.call_count, 0)
        first = self.post(body)
        second = self.post(body)
        self.assertEqual(first[0], 200)
        self.assertEqual(first[1], second[1])
        self.assertEqual(first[2], "trace-test")
        self.assertEqual(self.process.call_count, 1)
        request = Request(self.url + "/internal/v3/invocations/i-http", headers={"X-Agent-Key": "test-key-only"})
        with urlopen(request, timeout=5) as response:
            self.assertEqual(json.load(response)["data"]["status"], "FINISHED")

    def test_concurrent_model_requests_are_bounded(self):
        import threading
        entered, release = threading.Event(), threading.Event()
        def slow(body):
            entered.set()
            release.wait(4)
            return {"code": "OK", "message": "mock", "data": None}
        self.process.side_effect = slow
        first = threading.Thread(target=lambda: self.post({"task": {"invocationId": "busy-1"}}))
        first.start()
        try:
            self.assertTrue(entered.wait(2))
            status, body, _ = self.post({"task": {"invocationId": "busy-2"}})
            self.assertEqual(status, 429)
            self.assertEqual(body["code"], "RATE_LIMITED")
            self.assertEqual(self.process.call_count, 1)
            self.assertEqual(self.store.get("busy-2")["status"], "FAILED")
        finally:
            release.set()
            first.join(5)


if __name__ == "__main__":
    unittest.main()
