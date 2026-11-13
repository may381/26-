"""Local-only HTTP smoke check. Python 3.8+, standard library only."""
import json
import socket
import uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


def main():
    root = Path(__file__).resolve().parent
    try:
        key = (root / '.a1-service-key').read_text().strip()
        payload = json.loads((root / 'example_invocation.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        print('缺少密钥文件或示例请求文件，请确认本文件上传到 yinling-a1 目录。')
        return 1
    suffix = uuid.uuid4().hex
    payload['conversationId'] = 'conv-' + suffix
    payload['messageId'] = 'msg-' + suffix
    payload['task']['id'] = 'task-' + suffix
    payload['task']['invocationId'] = 'invoke-' + suffix
    payload['task']['deadlineAt'] = (datetime.now(timezone.utc) + timedelta(minutes=3)).isoformat()
    request = Request('http://127.0.0.1:8093/internal/v3/messages',
                      data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                      headers={'Content-Type': 'application/json', 'X-Agent-Key': key,
                               'X-Agent-Protocol-Version': '3.0'}, method='POST')
    print('正在测试本机 A1 接口，等待模型回复（最多约 110 秒）……', flush=True)
    print('调用 ID：' + payload['task']['invocationId'], flush=True)
    try:
        with urlopen(request, timeout=110) as response:
            result = json.load(response)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except HTTPError as error:
        print('HTTP 状态：', error.code)
        print(error.read().decode('utf-8', errors='replace'))
        return 1
    except (URLError, socket.timeout, ValueError) as error:
        print('测试未完成：', type(error).__name__)
        print('请检查服务日志；超时后不要立即重复提交，可使用上方调用 ID 查询回执。')
        return 1
    print('本次仅测试接口与模型，不执行报名、通知或长期记忆写入。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
