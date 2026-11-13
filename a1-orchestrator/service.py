"""A1 HTTP integration shell. No business writes or real delegation gateway yet."""
import hashlib
import hmac
import json
import os
import re
import sqlite3
import threading
import importlib.metadata
from pathlib import Path
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from v3_adapter import handle


def now():
    return datetime.now(timezone.utc).isoformat()


def load_service_key(path=None):
    """Use explicit environment first, then the previously created private key file."""
    key = os.environ.get("A1_SERVICE_KEY")
    if key is None:
        target = Path(path) if path is not None else Path(__file__).resolve().parent / ".a1-service-key"
        try:
            if os.name == "posix" and target.stat().st_mode & 0o077:
                raise SystemExit("密钥文件权限过宽，请设置为600后启动")
            if target.stat().st_size > 512:
                raise SystemExit("密钥文件格式无效")
            key = target.read_text(encoding="ascii").strip()
        except (OSError, UnicodeError):
            raise SystemExit("缺少私有密钥文件或A1_SERVICE_KEY，未启动服务")
    if not 24 <= len(key) <= 512 or any(ord(char) < 33 or ord(char) > 126 for char in key):
        raise SystemExit("服务密钥需为24至512个可打印ASCII字符，不含空格或换行")
    return key


class Receipts:
    def __init__(self, path):
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("CREATE TABLE IF NOT EXISTS calls (id TEXT PRIMARY KEY, digest TEXT, status TEXT, result TEXT, error TEXT, received TEXT, updated TEXT)")
        self.db.execute("CREATE TABLE IF NOT EXISTS cancels (request_id TEXT PRIMARY KEY, call_id TEXT, digest TEXT, response TEXT)")
        # Do not blindly restart an invocation interrupted by process shutdown.
        error = json.dumps({"code": "UPSTREAM_ERROR", "message": "进程重启，旧调用需由P2核查后决定恢复", "retryable": False}, ensure_ascii=False)
        self.db.execute("UPDATE calls SET status='FAILED', error=?, updated=? WHERE status IN ('RUNNING','RECEIVED','CANCEL_REQUESTED')", (error, now()))
        self.db.commit()
        if path != ":memory:":
            os.chmod(path, 0o600)

    def begin(self, iid, request):
        normalized = dict(request)
        normalized.pop("capabilityToken", None)
        digest = hashlib.sha256(json.dumps(normalized, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        with self.lock:
            row = self.db.execute("SELECT * FROM calls WHERE id=?", (iid,)).fetchone()
            if row:
                return "REPLAY" if row["digest"] == digest else "CONFLICT"
            stamp = now()
            self.db.execute("INSERT INTO calls VALUES (?,?,?,NULL,NULL,?,?)", (iid, digest, "RUNNING", stamp, stamp))
            self.db.commit()
            return "NEW"

    def get(self, iid):
        with self.lock:
            row = self.db.execute("SELECT * FROM calls WHERE id=?", (iid,)).fetchone()
            if not row:
                return None
            return {"invocationId": iid, "status": row["status"],
                    "result": json.loads(row["result"]) if row["result"] else None,
                    "error": json.loads(row["error"]) if row["error"] else None,
                    "receivedAt": row["received"], "updatedAt": row["updated"]}

    def finish(self, iid, result):
        with self.lock:
            row = self.get(iid)
            if row["status"] == "CANCEL_REQUESTED":
                self.db.execute("UPDATE calls SET status='CANCELLED',result=NULL,error=NULL,updated=? WHERE id=?", (now(), iid))
                self.db.commit()
                return False
            success = result.get("code") == "OK"
            error = None if success else {"code": result["code"], "message": result["message"], "retryable": False}
            self.db.execute("UPDATE calls SET status=?,result=?,error=?,updated=? WHERE id=?",
                            ("FINISHED" if success else "FAILED", json.dumps(result, ensure_ascii=False) if success else None,
                             json.dumps(error, ensure_ascii=False) if error else None, now(), iid))
            self.db.commit()
            return True

    def cancel(self, iid, request):
        digest = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
        key = request["cancelRequestId"]
        with self.lock:
            old = self.db.execute("SELECT * FROM cancels WHERE request_id=?", (key,)).fetchone()
            if old:
                if old["call_id"] != iid or old["digest"] != digest:
                    raise ValueError("CONFLICT")
                return json.loads(old["response"])
            row = self.get(iid)
            if not row:
                return None
            status = row["status"]
            if status in ("RECEIVED", "RUNNING"):
                status = "CANCEL_REQUESTED"
                self.db.execute("UPDATE calls SET status=?,updated=? WHERE id=?", (status, now(), iid))
            data = {"invocationId": iid, "cancelRequestId": key, "status": status,
                    "lastProgressSeq": 0, "reconciliationRequired": False}
            self.db.execute("INSERT INTO cancels VALUES (?,?,?,?)", (key, iid, digest, json.dumps(data)))
            self.db.commit()
            return data


def envelope(code, message, data=None):
    return {"code": code, "message": message, "data": data}


def health_data():
    """Return non-secret deployment facts useful during P2/A1 integration."""
    try:
        graph_version = importlib.metadata.version("langgraph")
    except importlib.metadata.PackageNotFoundError:
        graph_version = None
    return {
        "mode": "INTEGRATION_SHELL",
        "protocolVersion": "3.0",
        "inboundReady": True,
        "p2OutboundConfigured": bool(os.environ.get("A1_AGENT_KEY")),
        "modelEndpointConfigured": bool(os.environ.get("A1_MODEL_URL")),
        "langGraphVersion": graph_version,
    }


def make_handler(receipts, key, process=handle):
    model_slot = threading.BoundedSemaphore(1)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Do not log request bodies, query credentials or model text.

        def send_json(self, status, body):
            raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("X-Agent-Protocol-Version", "3.0")
            trace = self.headers.get("X-Trace-Id", "")
            if re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", trace):
                self.send_header("X-Trace-Id", trace)
            self.end_headers()
            try:
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError):
                pass  # Receipt stays available even if the caller disconnects.

        def authorized(self):
            supplied = self.headers.get("X-Agent-Key", "")
            if not hmac.compare_digest(supplied.encode(), key.encode()):
                self.send_json(401, envelope("UNAUTHORIZED", "服务密钥缺失或错误"))
                return False
            return True

        def read_json_body(self, maximum=1024 * 1024):
            """Accept fixed-length and RFC 7230 chunked JSON bodies from P2."""
            transfer = self.headers.get("Transfer-Encoding", "").lower()
            if transfer == "chunked":
                raw = bytearray()
                while True:
                    line = self.rfile.readline(128)
                    if not line:
                        raise ValueError()
                    size = int(line.split(b";", 1)[0].strip(), 16)
                    if size == 0:
                        while self.rfile.readline(8192) not in (b"\r\n", b"\n", b""):
                            pass
                        break
                    if size < 0 or len(raw) + size > maximum:
                        raise ValueError()
                    chunk = self.rfile.read(size)
                    if len(chunk) != size or self.rfile.read(2) != b"\r\n":
                        raise ValueError()
                    raw.extend(chunk)
                if not raw:
                    raise ValueError()
            else:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= maximum:
                    raise ValueError()
                raw = self.rfile.read(size)
                if len(raw) != size:
                    raise ValueError()
            value = json.loads(raw.decode("utf-8"))
            if not isinstance(value, dict):
                raise ValueError()
            return value

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == "/health":
                self.send_json(200, envelope("OK", "A1 v3入站服务可用", health_data()))
                return
            if not self.authorized():
                return
            match = re.fullmatch(r"/internal/v3/invocations/([A-Za-z0-9._:-]{1,128})", path)
            data = receipts.get(match.group(1)) if match else None
            self.send_json(200 if data else 404, envelope("OK", "调用记录", data) if data else envelope("NOT_FOUND", "调用记录不存在"))

        def do_POST(self):
            if not self.authorized():
                return
            self.connection.settimeout(15)
            try:
                body = self.read_json_body()
            except (ValueError, UnicodeError, OSError):
                self.send_json(400, envelope("INVALID_ARGUMENT", "请求必须是有效JSON对象且不超过1MiB"))
                return
            path = urlsplit(self.path).path
            cancel = re.fullmatch(r"/internal/v3/invocations/([A-Za-z0-9._:-]{1,128})/cancel", path)
            if cancel:
                if (set(body) != {"protocolVersion", "invocationId", "cancelRequestId", "reason"}
                        or body.get("protocolVersion") != "3.0" or body.get("invocationId") != cancel.group(1)
                        or not isinstance(body.get("cancelRequestId"), str) or not 0 < len(body["cancelRequestId"]) <= 128
                        or not isinstance(body.get("reason"), str) or not 0 < len(body["reason"]) <= 500):
                    self.send_json(400, envelope("INVALID_ARGUMENT", "取消字段无效"))
                    return
                try:
                    data = receipts.cancel(cancel.group(1), body)
                    self.send_json(200 if data else 404, envelope("OK", "取消控制请求已记录", data) if data else envelope("NOT_FOUND", "调用记录不存在"))
                except ValueError:
                    self.send_json(409, envelope("CONFLICT", "取消请求ID已用于不同内容"))
                return
            if path != "/internal/v3/messages":
                self.send_json(404, envelope("NOT_FOUND", "接口不存在"))
                return
            task = body.get("task")
            iid = task.get("invocationId") if isinstance(task, dict) else None
            if not isinstance(iid, str) or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", iid):
                self.send_json(400, envelope("INVALID_ARGUMENT", "invocationId无效"))
                return
            mode = receipts.begin(iid, body)
            if mode == "CONFLICT":
                self.send_json(409, envelope("CONFLICT", "相同调用ID的内容不一致"))
                return
            if mode == "REPLAY":
                old = receipts.get(iid)
                if old["status"] == "FINISHED":
                    self.send_json(200, old["result"])
                else:
                    self.send_json(409, envelope("CONFLICT", "该调用已登记；请GET调用记录核查，不重复启动"))
                return
            if not model_slot.acquire(blocking=False):
                result = envelope("RATE_LIMITED", "A1正在处理其他调用，请先查回执再由P2安排重试")
                receipts.finish(iid, result)
                self.send_json(429, result)
                return
            try:
                try:
                    result = process(body)
                except Exception:
                    result = envelope("INTERNAL_ERROR", "A1处理异常，未执行业务")
            finally:
                model_slot.release()
            if not receipts.finish(iid, result):
                self.send_json(409, envelope("TASK_NOT_RUNNABLE", "调用已取消，结果未交付"))
                return
            code = result.get("code")
            status = {"OK": 200, "INVALID_ARGUMENT": 400, "UNSUPPORTED_PROTOCOL_VERSION": 400,
                      "FORBIDDEN": 403, "UPSTREAM_TIMEOUT": 504, "CAPABILITY_UNAVAILABLE": 503,
                      "INTERNAL_ERROR": 500}.get(code, 502)
            self.send_json(status, result)

    return Handler


def main():
    key = load_service_key()
    host = os.environ.get("A1_BIND", "127.0.0.1")
    port = int(os.environ.get("A1_PORT", "8093"))
    receipts = Receipts(os.environ.get("A1_RECEIPT_DB", "a1-receipts.sqlite3"))
    server = ThreadingHTTPServer((host, port), make_handler(receipts, key))
    server.daemon_threads = True
    print("A1接口联调壳已启动：http://%s:%s；未接通P2委派，非完整v3服务" % (host, port), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
