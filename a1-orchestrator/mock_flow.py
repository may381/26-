"""Separate local HTTP mock harness, NOT the production v3 API."""
import copy
import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen
from demo import DemoSession


class Flow:
    def __init__(self, planner=None):
        self.sessions = {}
        self.receipts = {}
        self.lock = threading.RLock()
        self.planner = planner

    def handle(self, body):
        with self.lock:
            sid, rid, text = body['sessionId'], body['requestId'], body['text']
            if not all(isinstance(v, str) and v for v in (sid, rid, text)) or len(text) > 2000:
                raise ValueError('invalid input')
            key = (sid, rid)
            if key in self.receipts:
                old_text, result = self.receipts[key]
                if old_text != text:
                    raise ValueError('REQUEST_ID_CONFLICT')
                return copy.deepcopy(result)
            session = self.sessions.setdefault(sid, DemoSession(self.planner))
            reply = session.send(text)
            result = {'mode': 'LOCAL_MOCK_NOT_V3', 'sessionId': sid,
                      'requestId': rid, 'reply': reply, 'snapshot': session.snapshot()}
            self.receipts[key] = (text, copy.deepcopy(result))
            return result


def make_server(flow):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            if self.path != '/mock/messages':
                self.send_error(404)
                return
            try:
                self.connection.settimeout(10)
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 16384:
                    raise ValueError('invalid size')
                result = flow.handle(json.loads(self.rfile.read(size)))
                status = 200
            except Exception:
                status, result = 400, {'error': 'MOCK_REQUEST_FAILED', 'realBusinessExecuted': False}
            raw = json.dumps(result, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
    return ThreadingHTTPServer(('127.0.0.1', 0), Handler)


def main():
    flow = Flow()
    server = make_server(flow)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    sid = uuid.uuid4().hex
    url = 'http://127.0.0.1:%s/mock/messages' % server.server_port
    print('本地 HTTP mock 闭环：模型真实调用，P2/A2/A3 为内存替身。')
    print('依次输入需求、城市、课程编号、同意或拒绝。/status 查看，/cancel 取消，/exit 退出。')
    print('服务端口自动分配，不影响现有 8093 服务；退出后演示状态清空。')
    try:
        while True:
            text = input('老人：').strip()
            if text == '/exit':
                break
            if text == '/status':
                session = flow.sessions.get(sid)
                print(json.dumps(session.snapshot() if session else {}, ensure_ascii=False, indent=2))
                continue
            if not text:
                continue
            body = {'sessionId': sid, 'requestId': uuid.uuid4().hex, 'text': text}
            print('处理中……', flush=True)
            try:
                request = Request(url, data=json.dumps(body).encode(),
                                  headers={'Content-Type': 'application/json'}, method='POST')
                with urlopen(request, timeout=110) as response:
                    result = json.load(response)
                print('小颐：' + result['reply'])
                print('任务状态：' + result['snapshot']['state'])
            except Exception:
                print('本轮失败；演示服务不执行任何真实业务。')
    except (EOFError, KeyboardInterrupt):
        pass
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
