"""Local unified Q&A preview; delegates to existing A1 and domain services."""
import json
import os
import sys
import secrets
import time
import threading
import re
import base64
import binascii
from urllib.request import urlopen, Request
from urllib.parse import parse_qs
from pathlib import Path
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, urlencode

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'a1-orchestrator'))
from domain_chat import DomainChat
from local_domains import DomainError
from a1 import PlanningError
import payment_guard
import tickets
from p2_public import P2PublicClient, P2PublicError
from p2_session import P2TaskSession
from urllib.error import HTTPError

sessions={}
sessions_lock=threading.Lock()

def new_p2_session():
    user_id=os.environ.get('A1_P2_USER_ID','').strip()
    if not user_id:return None
    base=os.environ.get('A1_P2_PUBLIC_URL','http://127.0.0.1:8080')
    return P2TaskSession(P2PublicClient(base=base),user_id)

def p2_default_enabled():
    return os.environ.get('A1_P2_DEFAULT','').strip().lower() in ('1','true','yes','on')

def p2_packet(result,p2):
    result=result if isinstance(result,dict) else {}
    state=result.get('status',result.get('taskStatus','QUEUED'))
    reply=result.get('reply')
    if isinstance(reply,dict):reply=reply.get('text')
    pending_inputs=result.get('pendingInputRequests',[])
    if state=='WAITING_INPUT' and pending_inputs and isinstance(pending_inputs[0],dict):
        question=pending_inputs[0].get('question')
        if isinstance(question,str) and question.strip():reply=question
    if not isinstance(reply,str) or not reply.strip():
        reply={'QUEUED':'任务已由P2接收，正在排队。','RUNNING':'总智能体正在处理。',
               'WAITING_DEPENDENCIES':'正在等待协作结果。','WAITING_INPUT':'还需要您补充信息。',
               'WAITING_CONFIRMATION':'有操作需要您逐项确认。','CANCEL_REQUESTED':'正在停止后续处理。',
               'CANCELLED':'任务已取消。','SUCCEEDED':'任务已经完成。',
               'PARTIALLY_SUCCEEDED':'任务部分完成，请查看未完成事项。','FAILED':'任务未完成。'}.get(state,'P2任务状态已更新。')
    return {'mode':'P2_V3','reply':reply,'state':state,'domainResult':result,
            'conversationId':p2.conversation_id,'taskId':p2.task_id,'taskVersion':p2.task_version,
            'confirmationIds':result.get('confirmationIds',[]),
            'pendingInputRequests':pending_inputs}

# 案例库：5 类高发诈骗是目标；只展示有可核实来源的条目，缺的明说缺。
CASE_TARGETS=('冒充客服退款','投资理财','兼职刷单','婚恋交友','冒充公检法')

def fraud_cases():
    items=[]
    origin=None
    try:
        with urlopen('http://127.0.0.1:8000/api/knowledge/cases',timeout=3) as response:
            rows=json.loads(response.read(400001))
        for row in rows if isinstance(rows,list) else []:
            if not isinstance(row,dict) or not row.get('content'):continue
            items.append({'id':str(row.get('id','')),'type':str(row.get('fraud_type','未分类')),
                          'title':str(row.get('fraud_type','未分类')),'content':str(row['content']),
                          'source':str(row.get('source_name','') or '')})
        if items:
            origin='反诈后端已审核案例'
    except Exception:
        pass
    if not items:
        # 后端没起、或后端可用但没有已审核案例时，回退到同一份来源文件。
        origin='随应用发布的内置案例（与反诈后端同一份来源文件）'
        try:
            fixture=json.loads((ROOT/'data'/'fraud-cases.json').read_text(encoding='utf-8'))
        except (OSError,ValueError):
            fixture=[]
        for case in fixture if isinstance(fixture,list) else []:
            if not isinstance(case,dict) or not case.get('content'):continue
            items.append({'id':str(case.get('id','')),'type':str(case.get('type','未分类')),
                          'title':str(case.get('title','未分类')),'content':str(case['content']),
                          'source':str(case.get('source','') or '')})
    present={t for t in CASE_TARGETS if any(t in (i['type']+i['title']) for i in items)}
    return {'items':items,'count':len(items),'origin':origin,
            'target':len(CASE_TARGETS),'covered':sorted(present),
            'missing':[t for t in CASE_TARGETS if t not in present],
            'notice':'缺的类别需要可核实来源后再补；不编案例。'}


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def respond(self,status,data,cookie=None):
        raw=json.dumps(data,ensure_ascii=False).encode()
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store')
        if cookie:self.send_header('Set-Cookie','a1new='+cookie+'; HttpOnly; SameSite=Strict; Path=/')
        self.end_headers()
        try:self.wfile.write(raw)
        except (BrokenPipeError,ConnectionResetError):pass
    def tourism_proxy(self):
        target=self.path.removeprefix('/tourism-api')
        if not target.startswith('/api/a1/') or '..' in target:
            self.respond(400,{'error':'无效旅游接口'});return
        try:
            size=int(self.headers.get('Content-Length','0'))
            if size<0 or size>12000000:raise ValueError()
            body=self.rfile.read(size) if size else None
            headers={'Content-Type':self.headers.get('Content-Type','application/json')}
            if self.headers.get('Cookie'):headers['Cookie']=self.headers['Cookie']
            req=Request('http://127.0.0.1:8091'+target,data=body,headers=headers,method=self.command)
            try:response=urlopen(req,timeout=240)
            except HTTPError as error:response=error
            with response:
                raw=response.read(16000001)
                if len(raw)>16000000:raise ValueError()
                self.send_response(response.status)
                self.send_header('Content-Type',response.headers.get('Content-Type','application/json'))
                for cookie in response.headers.get_all('Set-Cookie',[]):self.send_header('Set-Cookie',cookie)
                self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
        except Exception:self.respond(502,{'error':'旅游后端8091未返回有效结果'})
    def do_PUT(self):
        if self.path.startswith('/tourism-api/'):return self.tourism_proxy()
        self.respond(404,{'error':'接口不存在'})
    def do_GET(self):
        path=urlsplit(self.path).path
        if path.startswith('/tourism-api/'):return self.tourism_proxy()
        if path.startswith('/tourism/'):
            name=path.removeprefix('/tourism/') or 'index.html'
            if '/' in name or name not in {p.name for p in (ROOT/'tourism').iterdir() if p.is_file()}:
                self.respond(404,{'error':'页面不存在'});return
            import mimetypes
            raw=(ROOT/'tourism'/name).read_bytes();self.send_response(200);self.send_header('Content-Type',(mimetypes.guess_type(name)[0] or 'application/octet-stream')+'; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw);return
        if path=='/api/a1/map-config' or path.startswith('/_AMapService/'):
            try:
                if '..' in self.path or len(self.path)>12000:raise ValueError()
                with urlopen('http://127.0.0.1:8091'+self.path,timeout=20) as response:
                    raw=response.read(5000001);mime=response.headers.get('Content-Type','application/octet-stream')
                if len(raw)>5000000:raise ValueError()
                self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
            except Exception:self.respond(502,{'error':'高德交互地图服务不可用，请检查8091服务'})
            return
        if path=='/api/map-image':
            query=parse_qs(urlsplit(self.path).query);identity=query.get('id',[''])[0]
            if not re.fullmatch(r'[A-Za-z0-9]{5,40}',identity):self.respond(400,{'error':'地图地点无效'});return
            try:
                with urlopen('http://127.0.0.1:8091/api/a1/map-image?'+urlencode({'id':identity,'zoom':12}),timeout=20) as response:
                    content=response.read(3000001);mime=response.headers.get('Content-Type','')
                if not mime.startswith('image/') or len(content)>3000000:raise ValueError()
                self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(content)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(content)
            except Exception:self.respond(502,{'error':'地图预览暂不可用，请使用高德地图入口'})
            return
        if path=='/api/system-status':
            import socket
            from concurrent.futures import ThreadPoolExecutor
            def probe(item):
                name,host,port=item
                try:
                    with socket.create_connection((host,port),timeout=2):available=True
                except OSError:available=False
                return {'name':name,'reachable':available,'scope':'端口可达，不代表模型推理或业务成功'}
            targets=[('A1任务服务','127.0.0.1',8093),('P2任务网关','127.0.0.1',8080),
                     ('旅游后端','127.0.0.1',8091),('反诈后端','127.0.0.1',8000),
                     ('学校模型','10.138.50.151',8000)]
            with ThreadPoolExecutor(max_workers=len(targets)) as pool:
                checks=list(pool.map(probe,targets))
            self.respond(200,{'checks':checks,'mode':'本地A1协调器，非P2正式网关','memory':'本次会话内存；长期共享记忆尚未接通'});return
        if path=='/api/health':
            self.respond(200,{'model':'qwen3.8-27b','provider':'school','modelVerified':False});return
        if path=='/api/fraud-cases':
            self.respond(200,fraud_cases());return
        files={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/tools.js':('tools.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}
        files.update({'/exchange.css':('assets/exchange.css','text/css; charset=utf-8'),'/exchange.js':('assets/exchange.js','text/javascript; charset=utf-8')})
        files.update({'/reference-chat.css':('reference-chat.css','text/css; charset=utf-8'),'/travel-flow.js':('travel-flow.js','text/javascript; charset=utf-8')})
        files['/mobile-app.css']=('mobile-app.css','text/css; charset=utf-8')
        files['/agent-trace.js']=('agent-trace.js','text/javascript; charset=utf-8')
        files['/native-tourism.js']=('native-tourism.js','text/javascript; charset=utf-8')
        files['/tourism-entry.js']=('tourism-entry.js','text/javascript; charset=utf-8')
        files['/interactive-map.js']=('interactive-map.js','text/javascript; charset=utf-8')
        files['/ticket-ui.js']=('ticket-ui.js','text/javascript; charset=utf-8')
        files['/fraud-result.js']=('fraud-result.js','text/javascript; charset=utf-8')
        files['/fraud-ui.js']=('fraud-ui.js','text/javascript; charset=utf-8')
        files['/rich-replies.js']=('rich-replies.js','text/javascript; charset=utf-8')
        files['/payment-guard.html']=('payment-guard.html','text/html; charset=utf-8')
        files['/cases.html']=('cases.html','text/html; charset=utf-8')
        files['/payment-guard-ui.js']=('payment-guard-ui.js','text/javascript; charset=utf-8')
        files['/wait-feedback.js']=('wait-feedback.js','text/javascript; charset=utf-8')
        files.update({'/restart.css':('restart.css','text/css; charset=utf-8'),'/restart.js':('restart.js','text/javascript; charset=utf-8'),'/previous':('index-before-restart.html','text/html; charset=utf-8')})
        if path not in files:self.respond(404,{'error':'页面不存在'});return
        name,mime=files[path];raw=(ROOT/name).read_bytes();self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-cache');self.end_headers();self.wfile.write(raw)
    def do_POST(self):
        if self.headers.get('Origin') not in (None,'http://127.0.0.1:8095','http://localhost:8095'):
            self.respond(403,{'error':'请求来源不允许'});return
        path=urlsplit(self.path).path
        if path.startswith('/tourism-api/'):return self.tourism_proxy()
        if path not in ('/api/message','/api/status','/api/reset','/api/image','/api/tool','/api/payment-guard',
                        '/api/p2/message','/api/p2/status','/api/p2/cancel','/api/p2/reset',
                        '/api/p2/confirmation','/api/p2/confirmation-decision','/api/p2/image',
                        '/api/p2/restore'):
            self.respond(404,{'error':'接口不存在'});return
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=6000000:raise ValueError()
            body=json.loads(self.rfile.read(length))
            if not isinstance(body,dict):raise ValueError()
        except (ValueError,TypeError):self.respond(400,{'error':'请求格式或大小不正确'});return
        if path=='/api/payment-guard':
            # 纯规则、不调模型、不建会话：老人转账前的一句核对。
            text=body.get('text')
            if not isinstance(text,str) or not text.strip() or len(text)>5000:self.respond(400,{'error':'文本无效或超长'});return
            self.respond(200,payment_guard.check(text) or {'triggered':False});return
        cookies=SimpleCookie()
        try:cookies.load(self.headers.get('Cookie',''))
        except Exception:pass
        sid=cookies['a1new'].value if 'a1new' in cookies else None
        with sessions_lock:
            for key in list(sessions):
                if time.monotonic()-sessions[key]['at']>3600 and not sessions[key]['lock'].locked():del sessions[key]
            if sid not in sessions:
                if len(sessions)>=50:self.respond(429,{'error':'会话数量已满，请稍后再试'});return
                sid=secrets.token_urlsafe(32);sessions[sid]={'chat':DomainChat(),'p2':new_p2_session(),'lock':threading.Lock(),'at':time.monotonic()}
            session=sessions[sid];session['at']=time.monotonic()
        if not session['lock'].acquire(blocking=False):self.respond(409,{'error':'当前对话仍在处理中，请等待结果'},sid);return
        chat=session['chat']
        try:
            if p2_default_enabled() and session['p2'] is not None:
                path={'/api/message':'/api/p2/message','/api/status':'/api/p2/status','/api/reset':'/api/p2/reset',
                      '/api/image':'/api/p2/image'}.get(path,path)
            if path.startswith('/api/p2/'):
                p2=session['p2']
                if p2 is None:
                    self.respond(503,{'error':'未配置A1_P2_USER_ID，P2正式任务模式未启用'},sid);return
                if path=='/api/p2/message':
                    text=body.get('text');continue_id=body.get('continueTaskId');response_to=body.get('responseTo')
                    if not isinstance(text,str):raise ValueError()
                    result=p2.submit(text,continue_task_id=continue_id,response_to=response_to)
                elif path=='/api/p2/image':
                    topic=body.get('topic');image=body.get('image')
                    text=body.get('text') or '请识别图片中可见的信息，并说明不确定之处。'
                    if topic not in ('fraud','tourism','auto') or not isinstance(text,str) or len(text)>1000 or not isinstance(image,str):raise ValueError()
                    match=re.fullmatch(r'data:(image/(?:png|jpeg));base64,([A-Za-z0-9+/=\r\n]+)',image)
                    if not match:raise ValueError()
                    try:content=base64.b64decode(match.group(2),validate=True)
                    except (ValueError,binascii.Error):raise ValueError() from None
                    purpose='fraud_analysis' if topic=='fraud' else 'travel_reference'
                    suffix='jpg' if match.group(1)=='image/jpeg' else 'png'
                    uploaded=p2.upload_image(purpose,'a1-upload.'+suffix,match.group(1),content)
                    result=p2.submit(text,attachment_ids=[uploaded['attachmentId']])
                elif path=='/api/p2/status':result=p2.status()
                elif path=='/api/p2/restore':
                    result=p2.restore_latest()
                    if result is None:
                        self.respond(200,{'mode':'P2_V3','restored':False,'reply':'P2中没有可恢复的历史任务。'},sid);return
                elif path=='/api/p2/cancel':
                    reason=body.get('reason','用户取消')
                    if not isinstance(reason,str):raise ValueError()
                    result=p2.cancel(reason)
                elif path=='/api/p2/reset':
                    p2.reset_local_reference();result={'reset':True,'notice':'仅清除本机会话引用，未取消P2后台任务'}
                elif path=='/api/p2/confirmation':
                    confirmation_id=body.get('confirmationId')
                    if not isinstance(confirmation_id,str):raise ValueError()
                    result=p2.get_confirmation(confirmation_id)
                else:
                    confirmation_id=body.get('confirmationId');decision=body.get('decision');version=body.get('expectedVersion')
                    if not isinstance(confirmation_id,str) or not isinstance(decision,str):raise ValueError()
                    result=p2.decide_confirmation(confirmation_id,decision,version)
                if path in ('/api/p2/confirmation','/api/p2/confirmation-decision'):
                    self.respond(200,{'mode':'P2_CONFIRMATION','data':result},sid);return
                self.respond(200,p2_packet(result,p2),sid);return
            if path=='/api/tool':
                action=body.get('action');payload=body.get('payload',{})
                if not isinstance(payload,dict):raise ValueError()
                routes={'nearby':('GET','/api/a1/nearby'),'weather':('GET','/api/a1/weather'),'districts':('GET','/api/a1/districts'),'route-location':('POST','/api/a1/routes/from-location'), 'location':('POST','/api/a1/location'), 'exchange':('GET','/api/a1/exchange'), 'places':('GET','/api/a1/places'), 'transport':('GET','/api/a1/transport'),
                    'import':('POST','/api/a1/guide-imports/analyze'), 'link':('POST','/api/a1/guide-imports/read-link'),
                    'plan':('POST','/api/a1/travel-drafts'), 'restore':('GET','/api/a1/travel-drafts/current'),
                    'save':('PUT','/api/a1/travel-drafts/current')}
                if action in ('tickets','ticket-stations'):
                    result=tickets.search(payload) if action=='tickets' else tickets.stations(payload)
                    self.respond(200,result,sid);return
                if action not in routes:raise ValueError()
                method,target=routes[action]
                if method=='GET' and payload:target+='?'+urlencode(payload)
                value=chat.client.transport(method,target,None if method=='GET' else payload)
                if value.get('code')!='OK':raise DomainError('旅游工具未完成请求')
                result=value['data']
            elif path=='/api/reset':result=chat.send('/new')
            elif path=='/api/status':result=chat.send('/status')
            elif path=='/api/image':
                topic=body.get('topic');image=body.get('image');question=body.get('text') or '请识别图片中可见的信息，并说明不确定之处。'
                if not isinstance(image,str) or not image.startswith(('data:image/png;base64,','data:image/jpeg;base64,')) or not isinstance(question,str) or len(question)>1000:raise ValueError()
                if topic=='fraud':
                    value=chat.client.transport('POST','/api/image-analyses',{'image_data_url':image,'note':question,'username':'统一问答用户'})
                    result={'domain':'fraud','domainResult':value,'reply':'图片分析已返回。'}
                else:
                    value=chat.client.transport('POST','/api/a1/images/analyze',{'image':image,'question':question})
                    if value.get('code')!='OK':raise DomainError('图片服务未返回有效结果')
                    result={'domain':'tourism','domainResult':value['data'],'reply':'图片识别已返回。'}
            else:
                text=body.get('text');topic=body.get('topic','auto')
                if not isinstance(text,str) or not 0<len(text.strip())<=2000 or topic not in ('auto','tourism','fraud'):raise ValueError()
                if chat.state in ('WAIT_RESULT','SUBMISSION_UNCERTAIN'):result=chat.send(text)
                elif topic=='tourism':
                    chat.trace=[{'stage':'selection','label':'用户选择出行','status':'completed','detail':'按用户选择直接调用旅游服务；本轮不调用总模型分流。'},
                                {'stage':'dispatch','label':'请求旅游服务8091','status':'waiting','detail':'提交用户原文，等待领域服务响应。'}]
                    try:value=chat.client.tourism(text)
                    except DomainError:
                        chat.trace[-1]['status']='failed';raise
                    chat.trace[-1]['status']='completed'
                    result={'domain':'tourism','domainResult':value,'reply':'出行咨询已返回。','executionTrace':list(chat.trace)}
                elif topic=='fraud':
                    chat.trace=[{'stage':'selection','label':'用户选择防诈','status':'completed','detail':'按用户选择直接调用反诈服务；本轮不调用总模型分流。'},
                                {'stage':'dispatch','label':'提交反诈任务8000','status':'waiting','detail':'沿用幂等请求标识，等待受理确认。'}]
                    if chat.state in ('COMPLETE','FAILED'):
                        chat.client.new();chat.state='READY'
                    try:value=chat.client.fraud(text)
                    except DomainError:
                        if chat.client.pending is not None:chat.state='SUBMISSION_UNCERTAIN'
                        chat.trace[-1]['status']='uncertain' if chat.state=='SUBMISSION_UNCERTAIN' else 'failed'
                        raise
                    chat.trace[-1]['status']='completed'
                    chat.inputs=[text]
                    chat.task_domain='fraud'
                    chat.trace.append({'stage':'result','label':'等待反诈分析','status':'waiting','detail':'受理不是风险结论，正在等待领域模型结果。'})
                    chat.state='WAIT_RESULT';result=chat.packet('反诈请求已受理，正在等待分析结果。',domain='fraud',domainResult=value)
                else:result=chat.send(text)
            self.respond(200,result,sid)
        except P2PublicError as error:self.respond(502,{'error':str(error),'submissionUncertain':error.uncertain,'executionTrace':[]},sid)
        except (DomainError,PlanningError,tickets.TicketError) as error:self.respond(502,{'error':str(error),'submissionUncertain':chat.state=='SUBMISSION_UNCERTAIN','executionTrace':list(chat.trace)},sid)
        except ValueError:self.respond(400,{'error':'请检查文字长度、图片格式和咨询领域'},sid)
        except Exception:self.respond(502,{'error':'服务未返回有效结果，请检查对应服务；未假定处理成功。'},sid)
        finally:session['lock'].release()

if __name__=='__main__':
    ThreadingHTTPServer.allow_reuse_address=False
    print('时光链统一问答：http://127.0.0.1:8095/\n综合→学校模型规划；出行→8091；反诈→8000。Ctrl+C 停止。',flush=True)
    ThreadingHTTPServer(('127.0.0.1',8095),Handler).serve_forever()
