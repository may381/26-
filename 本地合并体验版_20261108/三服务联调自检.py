"""Smoke-test A1 -> tourism and A1 -> anti-fraud through the v3 HTTP entry."""
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def base_url(variable, default):
    value=os.environ.get(variable,default).strip().rstrip('/')
    parsed=urlsplit(value)
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.path not in ('','/'):
        raise SystemExit(variable+' 不是有效服务根地址')
    return value


A1=base_url('AGENT_A1_URL','http://127.0.0.1:8093')
TOURISM=base_url('A1_TOURISM_URL','http://127.0.0.1:8091')
FRAUD=base_url('A1_FRAUD_URL','http://127.0.0.1:8000')
KEY=os.environ.get('A1_SERVICE_KEY','').strip()


def get_json(url, timeout=8):
    with urlopen(url,timeout=timeout) as response:
        return response.status,json.load(response)


def invocation(text):
    suffix=uuid.uuid4().hex
    return {
        'protocolVersion':'3.0','userId':'merge-smoke-user',
        'conversationId':'conv-'+suffix,'messageId':'msg-'+suffix,
        'task':{'id':'task-'+suffix,'parentTaskId':None,'version':1,'attempt':1,
                'invocationId':'invoke-'+suffix,
                'deadlineAt':(datetime.now(timezone.utc)+timedelta(minutes=3)).isoformat()},
        'input':{'text':text,'attachmentIds':[]},
        'context':{'reason':'USER_MESSAGE','history':[]},
        'capabilityToken':'MERGE-SMOKE-NO-BUSINESS-WRITES',
    }


def call_a1(text, expected_type):
    body=invocation(text)
    request=Request(A1+'/internal/v3/messages',
                    data=json.dumps(body,ensure_ascii=False).encode('utf-8'),
                    headers={'Content-Type':'application/json','X-Agent-Key':KEY,
                             'X-Agent-Protocol-Version':'3.0',
                             'X-Trace-Id':body['task']['invocationId']},method='POST')
    with urlopen(request,timeout=115) as response:
        packet=json.load(response)
    if packet.get('code')!='OK' or not isinstance(packet.get('data'),dict):
        raise RuntimeError('A1 未返回成功报文：'+str(packet.get('code')))
    results=packet['data'].get('results',[])
    if not any(isinstance(item,dict) and item.get('type')==expected_type for item in results):
        raise RuntimeError('A1 未返回 '+expected_type+' 结果')
    return packet['data']


def main():
    if len(KEY)<16:
        print('请先设置 A1_SERVICE_KEY，且必须与启动 A1 时的密钥相同。',file=sys.stderr)
        return 2
    checks=[('A1',A1+'/health'),('反诈',FRAUD+'/api/health')]
    try:
        # Tourism has no dedicated health endpoint; its root page is a safe readiness probe.
        with urlopen(TOURISM+'/',timeout=8) as response:
            if response.status!=200:raise RuntimeError('旅游服务根页面状态异常')
        print('PASS 旅游服务可达：'+TOURISM)
        for name,url in checks:
            status,_=get_json(url)
            if status!=200:raise RuntimeError(name+'健康检查失败')
            print('PASS '+name+'服务健康检查：'+url)
        tourism=call_a1('请介绍长沙适合老人少走路、方便休息的真实景点','TOURISM_ADVICE')
        print('PASS A1 → 旅游：'+tourism['control']['outcome'])
        fraud=call_a1('有人自称客服，要求我提供短信验证码办理退款，请帮我核实风险','FRAUD_ANALYSIS')
        availability=fraud['results'][0].get('availability')
        if availability not in ('REAL','PENDING'):raise RuntimeError('反诈结果可用性字段异常')
        print('PASS A1 → 反诈：'+fraud['control']['outcome']+' / '+availability)
        print('三服务链路通过。PENDING 只表示任务仍在处理，不代表已经得到风险结论。')
        return 0
    except HTTPError as error:
        print('FAIL HTTP '+str(error.code)+'：'+error.read().decode('utf-8','replace')[:500],file=sys.stderr)
    except (URLError,TimeoutError,ValueError,RuntimeError) as error:
        print('FAIL '+str(error),file=sys.stderr)
    return 1


if __name__=='__main__':
    raise SystemExit(main())
