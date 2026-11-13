"""Opt-in school text generation check using synthetic input; no business writes."""
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, build_opener, ProxyHandler


def main():
    started = time.monotonic()
    report = {
        'checkedAt': datetime.now(timezone.utc).isoformat(),
        'model': 'qwen3.8-27b',
        'endpoint': 'http://10.138.50.151:8000/v1/chat/completions',
        'businessWrites': False,
        'scope': 'School text endpoint only; not application or P2 end-to-end acceptance.',
        'success': False,
    }
    payload = {
        'model': report['model'],
        'messages': [
            {'role': 'system', 'content': '请只输出一个JSON对象，不使用代码块。'},
            {'role': 'user', 'content': '这是一条合成的连通性测试。请输出字段status，其值为ok。'},
        ],
        'stream': False,
        'temperature': 0,
        'max_completion_tokens': 128,
        'chat_template_kwargs': {'enable_thinking': False},
    }
    request = Request(report['endpoint'],
                      data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                      headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with build_opener(ProxyHandler({})).open(request, timeout=15) as response:
            raw = response.read(1024 * 1024 + 1)
            report['httpStatus'] = response.status
        if len(raw) > 1024 * 1024:
            raise ValueError('Oversized response')
        result = json.loads(raw)
        choice = result['choices'][0]
        report['finishReason'] = choice.get('finish_reason')
        report['returnedModel'] = result.get('model')
        content = json.loads(choice['message']['content'])
        report['success'] = (choice.get('finish_reason') == 'stop'
                             and content == {'status': 'ok'}
                             and result.get('model') == report['model'])
        if not report['success']:
            report['error'] = 'MODEL_OR_OUTPUT_CONTRACT_MISMATCH'
    except Exception as error:
        report['error'] = type(error).__name__
    report['elapsedSeconds'] = round(time.monotonic() - started, 2)
    path = Path(__file__).resolve().parent / '学校模型实际生成验收.json'
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
