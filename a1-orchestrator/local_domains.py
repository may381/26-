"""Domain connector used by A1; endpoints come from trusted deployment config.

Defaults remain loopback for a one-machine rehearsal.  Operators may set
``A1_TOURISM_URL`` and ``A1_FRAUD_URL`` when services run on another machine.
No notifications, booking, payment, or memory writes are performed here.
"""
import json
import re
import uuid
import base64
import socket
import os
from http.client import HTTPException
from pathlib import Path
from http.cookiejar import CookieJar
from urllib.request import build_opener, HTTPCookieProcessor, ProxyHandler, Request, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit


class DomainError(Exception):
    pass


def _service_base(value, default, variable):
    raw=(value or default).strip().rstrip('/')
    parsed=urlsplit(raw)
    if (parsed.scheme not in ('http','https') or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment or parsed.path not in ('','/')):
        raise DomainError(variable+' 必须是可信的 HTTP(S) 服务根地址，且不能包含路径、账号或查询参数')
    try:
        parsed.port
    except ValueError:
        raise DomainError(variable+' 端口无效') from None
    return raw


def validate_tourism_result(value):
    if not isinstance(value,dict) or not isinstance(value.get('text'),str) or not value['text'].strip():
        raise DomainError('旅游服务未返回有效结果')
    stack=[value]
    mock_source=False
    while stack:
        item=stack.pop()
        if isinstance(item,dict):
            if isinstance(item.get('source'),str) and item['source'].strip().upper() in ('MOCK','DEMO','FIXTURE'):
                mock_source=True;break
            stack.extend(item.values())
        elif isinstance(item,list):stack.extend(item)
    if mock_source or re.search(r'演示资料|演示数据|演示园区|示例资料|尚未选中真实地点',value['text']):
        raise DomainError('旅游服务返回演示资料，未取得真实旅游查询结果')
    return value


def validate_analysis_status(value, identity, source=None):
    if not isinstance(identity,str) or not re.fullmatch(r'real-[A-Za-z0-9-]{1,120}',identity):
        raise DomainError('分析任务标识无效')
    if not isinstance(value,dict) or value.get('analysis_id')!=identity:
        raise DomainError('返回任务标识与当前任务不一致，未取得当前分析结果')
    state=value.get('status')
    if state not in ('queued','processing','completed','failed','interrupted'):
        raise DomainError('领域服务返回未知任务状态，不能视为完成')
    if state=='completed':
        result=value.get('result')
        if (not isinstance(result,dict) or result.get('id')!=identity
                or result.get('level') not in ('low','medium','high')
                or not isinstance(result.get('evidence'),str) or not result['evidence'].strip()
                or not isinstance(result.get('advice'),list) or not result['advice']
                or any(not isinstance(x,str) or not x.strip() for x in result['advice'])):
            raise DomainError('完成状态缺少有效分析结果，未取得分析结论')
        if source is not None:
            # A citation to a public case is not evidence of this user's history.
            evidence=result['evidence']
            # Only treat statements about this user/party as personal-history
            # claims.  Generic warnings such as "近期此类诈骗高发" describe a
            # public trend and must not be rejected merely because the source
            # message did not contain that wording.
            history_pattern=(
                r'[^。！？\n]*(?:(?:你|您|用户|当事人|该用户).{0,16}'
                r'(?:近期|曾经|此前|历史上|多次遭遇)|'
                r'(?:近期|曾经|此前|历史上|多次遭遇).{0,16}'
                r'(?:你|您|用户|当事人|该用户))[^。！？\n]*'
            )
            for claim in re.findall(history_pattern,evidence):
                if claim.strip() not in source:
                    raise DomainError('分析包含未核实的历史事实，未取得可信分析结论')
            items=result.get('evidenceItems',[])
            if not isinstance(items,list):
                raise DomainError('分析原文证据无效，未取得可信分析结论')
            for item in items:
                if not isinstance(item,dict):
                    raise DomainError('分析原文证据无效，未取得可信分析结论')
                excerpt=item.get('excerpt');start=item.get('start');end=item.get('end')
                if (not isinstance(excerpt,str) or not excerpt or excerpt not in source
                        or type(start) is not int or type(end) is not int
                        or not 0<=start<end<=len(source) or source[start:end]!=excerpt):
                    raise DomainError('分析原文证据不匹配，未取得可信分析结论')
        return value
    # Pending/failed responses must not expose stale conclusions or upstream error bodies.
    return {'analysis_id':identity,'status':state,'result':None}


class _NoRedirect(HTTPRedirectHandler):
    """A loopback backend must not redirect this client to another host."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class DomainClient:
    def __init__(self, transport=None, tourism_base=None, fraud_base=None):
        self.opener=build_opener(ProxyHandler({}),HTTPCookieProcessor(CookieJar()),_NoRedirect())
        self.transport=transport or self._request
        self.tourism_base=_service_base(tourism_base or os.environ.get('A1_TOURISM_URL'),
                                        'http://127.0.0.1:8091','A1_TOURISM_URL')
        self.fraud_base=_service_base(fraud_base or os.environ.get('A1_FRAUD_URL'),
                                      'http://127.0.0.1:8000','A1_FRAUD_URL')
        self.pending=None
        self.analysis_id=None
        self.analysis_text=None

    def _request(self, method, path, body=None, headers=None):
        if (not isinstance(path,str) or not path.startswith('/') or path.startswith('//')
                or any(c in path for c in ('\\','\r','\n','\t','#'))):
            raise DomainError('接口路径无效')
        tourism=path.startswith(('/api/agent/','/api/a1/'))
        origin=self.tourism_base if tourism else self.fraud_base
        try:
            request=Request(origin+path,method=method,
                            data=None if body is None else json.dumps(body,ensure_ascii=False).encode('utf-8'),
                            headers={'Content-Type':'application/json',**(headers or {})})
            if path.startswith(('/api/image-analyses','/api/a1/images/analyze')):
                timeout = 220
            elif path == '/api/agent/messages':
                try:
                    timeout = float(os.environ.get('A1_TOURISM_TIMEOUT_SECONDS', '15'))
                except ValueError:
                    raise DomainError('A1_TOURISM_TIMEOUT_SECONDS 配置无效') from None
                if not 1 <= timeout <= 20:
                    raise DomainError('旅游服务超时必须在1至20秒内，以符合P2调用期限')
            else:
                timeout = 100
            with self.opener.open(request,timeout=timeout) as response:
                raw=response.read(1024*1024+1)
                if len(raw)>1024*1024:raise DomainError('领域服务响应过大')
                result=json.loads(raw)
                if not isinstance(result,dict):raise DomainError('领域服务响应必须是对象')
                return result
        except HTTPError as error:
            # Never read or forward an upstream error body, even for known status codes.
            code=error.code
            error.close()
            messages={
                503:'领域服务暂不可用，请检查后端、校园内网或学校VPN及模型连接；未取得处理结果。',
                413:'提交内容超出服务限制，请缩减文字或裁剪图片后重试。',
                504:'领域服务处理超时，未取得结果；请稍后查询任务状态或重试。',
            }
            raise DomainError(messages.get(code,'领域服务请求失败，未假定业务成功。')) from None
        except (socket.timeout,TimeoutError):
            raise DomainError('领域服务等待响应超时，未取得处理结果。') from None
        except URLError as error:
            if isinstance(error.reason,(socket.timeout,TimeoutError)):
                raise DomainError('领域服务等待响应超时，未取得处理结果。') from None
            raise DomainError('无法连接'+('旅游服务' if tourism else '反诈服务')+'（'+origin+'），请检查服务地址、网络和后端状态。') from None
        except ValueError:
            raise DomainError('领域服务返回了无法解析的数据，未假定处理成功。') from None
        except (OSError,HTTPException):
            raise DomainError('领域服务连接中断，请核对服务状态；未获得处理结果。') from None
        except (TypeError,OverflowError):
            raise DomainError('领域请求格式无效，未取得处理结果。') from None

    def tourism(self,text,location=None):
        if not isinstance(text,str) or not text.strip() or len(text)>2000:
            raise DomainError('旅游咨询文本长度应为1～2000字符')
        body={'userId':'local-contest-user','text':text}
        if location is not None:
            if not isinstance(location,str) or not location.strip() or len(location)>100 or location not in text:
                raise DomainError('旅游地点缺少可信原文证据')
            body['context']={'location':location}
        result=self.transport('POST','/api/agent/messages',body)
        if not isinstance(result,dict) or result.get('code')!='OK' or not isinstance(result.get('data'),dict):
            raise DomainError('旅游服务未返回有效结果')
        return validate_tourism_result(result['data'])

    def places(self,query,city=None):
        """Return real AMap places with coordinates; never invent fallback points."""
        if not isinstance(query,str) or not query.strip() or len(query)>100:
            raise DomainError('地点查询文本长度应为1～100字符')
        if city is not None and (not isinstance(city,str) or len(city.strip())>50):
            raise DomainError('城市参数无效')
        path='/api/a1/places?query='+quote(query.strip(),safe='')
        if isinstance(city,str) and city.strip():
            path+='&city='+quote(city.strip(),safe='')
        result=self.transport('GET',path)
        if not isinstance(result,dict) or result.get('code')!='OK' or not isinstance(result.get('data'),dict):
            raise DomainError('地点查询未返回有效结果')
        data=result['data']
        if str(data.get('source','')).strip().upper()!='AMAP':
            raise DomainError('地点数据不是高德实时来源')
        if not isinstance(data.get('places'),list):
            raise DomainError('地点数据格式无效')
        places=[]
        for item in data['places'][:8]:
            if not isinstance(item,dict):continue
            name=item.get('name');address=item.get('address');location=item.get('location')
            if not isinstance(name,str) or not name.strip():continue
            if not isinstance(location,str) or not re.fullmatch(r'-?\d{1,3}(?:\.\d+)?,-?\d{1,3}(?:\.\d+)?',location):continue
            places.append({'name':name.strip()[:100],
                           'address':address.strip()[:200] if isinstance(address,str) and address.strip() else None,
                           'location':location,
                           'type':item['type'].strip()[:100] if isinstance(item.get('type'),str) and item['type'].strip() else None})
        return places

    def image(self,path,question='请识别图片中可见的文字、标识和景物，说明不确定之处。'):
        if not isinstance(question,str) or not 0<len(question.strip())<=1000:
            raise DomainError('图片问题应为1～1000字符')
        try:
            with Path(path).open('rb') as source:raw=source.read(4*1024*1024+1)
        except (OSError,TypeError,ValueError):raise DomainError('无法读取所选图片')
        mime='image/png' if raw.startswith(b'\x89PNG\r\n\x1a\n') else 'image/jpeg' if raw.startswith(b'\xff\xd8\xff') else None
        if not mime or len(raw)>4*1024*1024:raise DomainError('只接受4MB以内PNG/JPEG图片')
        result=self.transport('POST','/api/a1/images/analyze',{'image':'data:'+mime+';base64,'+base64.b64encode(raw).decode('ascii'),'question':question.strip()})
        if not isinstance(result,dict) or result.get('code')!='OK' or not isinstance(result.get('data'),dict) or not isinstance(result['data'].get('text'),str) or not result['data']['text'].strip():
            raise DomainError('图片服务未返回有效识别结果')
        return result['data']

    def fraud(self,text,retry=False):
        if retry:
            if self.pending is None:raise DomainError('没有待重试的提交')
        else:
            if self.analysis_id:raise DomainError('已有分析任务，请先查询结果')
            if self.pending is not None:raise DomainError('上次提交结果尚未确认，请先 /retry；放弃引用可用 /new，但不会取消后端任务')
            if not isinstance(text,str) or not text.strip() or len(text)>10000:raise DomainError('文本长度应为1～10000字符')
            self.pending=(text.strip(),'local-'+uuid.uuid4().hex)
        content,key=self.pending
        result=self.transport('POST','/api/analyses',{'text':content,'username':'本地比赛演示'}, {'Idempotency-Key':key})
        identity=result.get('analysis_id') if isinstance(result,dict) else None
        if not isinstance(identity,str) or not re.fullmatch(r'real-[A-Za-z0-9-]{1,120}',identity):
            raise DomainError('分析任务标识无效')
        self.analysis_id=identity
        self.analysis_text=content
        self.pending=None
        return {'mode':'LOCAL_DOMAIN_CONNECTOR','analysisId':identity,'state':'ACCEPTED','notice':'任务已受理，不代表已完成检测；未执行通知。'}

    def status(self):
        if not self.analysis_id:raise DomainError('尚无分析任务')
        result=self.transport('GET','/api/analyses/'+self.analysis_id)
        return validate_analysis_status(result,self.analysis_id,self.analysis_text)

    def new(self):
        """Drop local references only; never imply a remote cancellation."""
        self.analysis_id=None
        self.pending=None
        self.analysis_text=None


def main():
    client=DomainClient()
    print('A1 本地领域联通演练（非P2 v3）：/travel 文字；/fraud 可疑文字；/status；/retry；/new；/exit')
    while True:
        try:
            line=input('A1：').strip()
            if line=='/exit':return
            if line=='/new':
                client.new();print('仅清除本地当前任务与重试引用，不删除或取消后端任务。');continue
            if line.startswith('/image '):result=client.image(line[7:].strip().strip('"'))
            elif line.startswith('/travel '):result=client.tourism(line[8:])
            elif line.startswith('/fraud '):result=client.fraud(line[7:])
            elif line=='/retry':result=client.fraud('',retry=True)
            elif line=='/status':result=client.status()
            else:
                print('请明确选择 /travel 或 /fraud；不会猜测要执行的业务动作。');continue
            print(json.dumps(result,ensure_ascii=False,indent=2))
        except DomainError as error:print(str(error))
        except (EOFError,KeyboardInterrupt):return


if __name__=='__main__':main()
