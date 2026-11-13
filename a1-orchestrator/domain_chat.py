"""School-planned natural-language entry for existing local domains, not P2 v3."""
import json
import time
import copy
from a1 import Conversation, PlanningError
from local_domains import DomainClient, DomainError, validate_tourism_result, validate_analysis_status
from graph_runtime import build_graph
from threading import RLock


class DomainChat:
    def __init__(self, planner=None, client=None):
        self.conversation=Conversation(planner, max_text_length=10000)
        self.client=client or DomainClient()
        self.inputs=[]
        self.task_domain=None
        self.state='READY'
        self.trace=[]
        self._lock=RLock()
        self.graph=build_graph(self)

    def packet(self, reply, **fields):
        return {'mode':'LOCAL_A1_DOMAIN_COORDINATOR_NOT_P2', 'state':self.state,
                'reply':reply, **fields, 'notificationExecuted':False, 'sharedMemoryWritten':False, 'executionTrace':copy.deepcopy(self.trace)}

    def send(self, text):
        try:
            with self._lock:
                return self.graph.invoke({'text':text})['packet']
        except (PlanningError, DomainError):
            if not self.trace or self.trace[-1].get('status') not in ('failed','uncertain'):
                stage='result' if text=='/status' else 'dispatch'
                self.trace.append({'stage':stage,'label':'请求未完成','status':'failed',
                                   'detail':'未取得有效结果，没有假定业务成功。'})
            return self.packet('本次请求未完成，请核对服务状态后重试；未取得有效结果。',executed=False)

    def _prepare(self, text):
        if not isinstance(text,str) or not text.strip():
            return self.packet('请输入具体需求；空内容没有提交给学校模型。',executed=False)
        text=text.strip()
        if text.startswith('/image ') and self.state not in ('WAIT_RESULT','SUBMISSION_UNCERTAIN'):
            result=self.client.image(text[7:].strip().strip('"'))
            return self.packet('学校图片识别结果如下；不代表核实现场位置或执行业务。',domainResult=result)
        if text=='/overview':
            return self.packet('当前协调状态；此查询不调用模型，也不执行业务。',
                analysisId=self.client.analysis_id if isinstance(self.client.analysis_id,str) else None,
                submissionUncertain=self.state=='SUBMISSION_UNCERTAIN',
                inputCount=len(self.inputs))
        if text.startswith('/'):
            return self.packet('支持 /overview、/status、/retry、/new、/reset；未知控制命令不会提交给模型。',executed=False)
        if self.state in ('WAIT_RESULT','SUBMISSION_UNCERTAIN'):
            return self.packet('已有反诈请求，请先 /status 查询；受理不确定时用 /retry。/new 只放弃本地引用，不取消后台任务。')
        if len(text)>10000:
            return self.packet('累计需求超过10000字符，请精简或使用 /new 开始新需求；本轮没有调用模型或截断原文。',executed=False)
        return None

    def _status(self):
        result=validate_analysis_status(self.client.status(),self.client.analysis_id,
            '\n'.join(self.inputs) if self.task_domain=='fraud' else None)
        self.state={'completed':'COMPLETE','failed':'FAILED','interrupted':'FAILED'}.get(result['status'],'WAIT_RESULT')
        if not self.trace or self.trace[-1].get('stage')!='result':
            self.trace.append({'stage':'result','label':'查询反诈结果'})
        if self.trace:
            self.trace[-1]={**self.trace[-1],'status':'completed' if self.state=='COMPLETE' else 'failed' if self.state=='FAILED' else 'waiting','detail':'已取得领域分析结果，需结合原文核对。' if self.state=='COMPLETE' else '领域任务未完成，未生成风险结论。' if self.state=='FAILED' else '仍在等待领域服务返回结果。'}
            self.trace[-1]['label']='接收反诈分析结果' if self.state=='COMPLETE' else '查询反诈结果'
        return self.packet('原分析任务状态如下；结论以领域结果为准。',domainResult=result)

    def _retry(self):
        if getattr(self.client,'pending',None) is None:
            return self.packet('当前没有待重试的提交；不会新建任务。')
        self.trace.append({'stage':'retry','label':'复用原幂等键重试','status':'waiting','detail':'上一次提交未确认；复用原请求标识重试，不创建新任务。'})
        try:
            result=self.client.fraud('',retry=True)
        except DomainError:
            self.state='SUBMISSION_UNCERTAIN'
            self.trace[-1].update(status='uncertain',detail='重试后仍未确认受理；不要用新文本覆盖原请求。')
            raise
        self.trace[-1].update(status='completed',detail='原幂等键重试已确认受理；受理不是风险结论。')
        self.state='WAIT_RESULT'
        self.trace.append({'stage':'result','label':'等待反诈分析','status':'waiting','detail':'任务已受理，等待领域模型分析；受理不是风险结论。'})
        return self.packet('已用原内容和幂等键重新获取受理结果，尚未完成分析。',domainResult=result)

    def _reset(self):
        self.client.new(); self.conversation.reset(); self.inputs=[];self.task_domain=None;self.state='READY';self.trace=[]
        return self.packet('已清空A1当前需求与重试引用；不会取消或删除后端任务。')

    def _planning(self, text):
        self.trace=[{'stage':'received','label':'接收需求','status':'completed','detail':'文字已通过长度校验；使用本次会话上下文。'}]
        started=time.monotonic()
        try:
            # Plan in a candidate session: rejected rounds must not commit evidence.
            terminal=self.state in ('COMPLETE','FAILED')
            candidate=Conversation(self.conversation.planner, max_text_length=10000)
            if not terminal:
                candidate.history=copy.deepcopy(self.conversation.history)
                candidate.last_plan=copy.deepcopy(self.conversation.last_plan)
            plan=candidate.turn(text)
            domains=plan['domains']
            domain=domains[0] if len(domains)==1 else None
            executable=(plan['decision']=='ASK' or
                        (len(plan['steps'])==1 and plan['steps'][0]['agent']=='a1'
                         and domain in ('tourism','fraud')))
            switched=bool(executable and not terminal and self.task_domain
                          and domain and domain!=self.task_domain)
            if switched:
                # Old conversation may help detect a switch, but cannot authorize it.
                # Re-plan from current user text only; old locations are no evidence.
                candidate=Conversation(self.conversation.planner, max_text_length=10000)
                plan=candidate.turn(text)
                if plan['domains'] != [domain]:
                    raise PlanningError('新任务领域未确认，未修改原上下文')
            self._candidate_context=(candidate, terminal or switched)

        except PlanningError:
            self.trace.append({'stage':'planning','label':'学校模型理解与规划','status':'failed','detail':'模型调用或结构校验失败，没有执行领域任务。'})
            raise
        self.trace.append({'stage':'planning','label':'学校模型理解与规划','status':'completed','durationMs':round((time.monotonic()-started)*1000),'detail':'输出决策：'+plan['decision']+'；领域：'+', '.join(plan.get('domains',[]))})
        return plan

    def _validation(self, text, plan):
        self.trace.append({'stage':'validation','label':'程序校验任务计划','status':'completed','detail':'检查任务字段、领域归属、依赖顺序与位置原文，不执行模型生成的URL或命令。'})
        if plan['decision']!='PLAN':
            self._commit_context(text, plan)
            return self.packet(plan['reply'],planned=False,memoryCandidateSaved=False)
        steps=plan['steps']
        if len(steps)!=1 or steps[0]['agent']!='a1' or steps[0]['domain'] not in ('tourism','fraud'):
            return self.packet('当前仅接通单步旅游咨询和反诈文本分析。跨领域、多步骤及A2/A3委派仍需P2网关，未执行任何步骤。',planned=True,executed=False)
        domain=steps[0]['domain']
        # Pass user evidence, never model-generated goals, commands, URLs or claims.
        _,fresh=self._candidate_context
        evidence=[] if fresh else self.inputs if self.task_domain in (None,domain) else []
        source='\n'.join([*evidence,text.strip()])
        if len(source)>(2000 if domain=='tourism' else 10000):
            self.trace[-1].update(status='failed',detail='累计原文超出领域接口限制，未执行领域请求。')
            return self.packet('累计原文超出领域接口限制，请 /new 后提交较短需求；没有截断或改写原文。',executed=False)
        self._commit_context(text, plan)
        return {'domain':domain,'source':source}

    def _commit_context(self, text, plan):
        candidate,fresh=self._candidate_context
        if fresh:
            self.client.new()
            self.inputs=[]
            self.task_domain=None
            self.state='READY'
        # Keep the public Conversation object stable for existing callers.
        self.conversation.history=copy.deepcopy(candidate.history)
        self.conversation.last_plan=copy.deepcopy(candidate.last_plan)
        domains=plan['domains']
        if len(domains)==1:
            domain=domains[0]
            if self.task_domain != domain:
                self.inputs=[]
            self.task_domain=domain
            self.inputs.append(text.strip())
        # General chat stays in conversation history, never in domain evidence.

    def _dispatch(self, domain, source):
        self.trace.append({'stage':'dispatch','label':'委派领域服务','status':'waiting','detail':'旅游 → 本机8091' if domain=='tourism' else '反诈 → 本机8000'})
        if domain=='tourism':
            try:
                if isinstance(self.client,DomainClient):
                    location=self.conversation.last_plan.get('location')
                    result=validate_tourism_result(self.client.tourism(source,location=location))
                else:
                    result=validate_tourism_result(self.client.tourism(source))
            except DomainError:
                self.trace[-1]['status']='failed'
                self.trace[-1]['detail']='旅游服务请求失败，没有返回可用结果。'
                raise
            self.trace[-1]['status']='completed'
            self.trace.append({'stage':'result','label':'接收旅游结果','status':'completed','detail':'收到领域服务响应；结果不代表预订或报名。'})
            return self.packet('旅游领域已返回咨询资料；尚未报名、预订或启动P2任务。',domain='tourism',domainResult=result)
        try:
            result=self.client.fraud(source)
        except DomainError:
            self.state='SUBMISSION_UNCERTAIN'
            self.trace[-1]['status']='uncertain'
            self.trace[-1]['detail']='未确认是否受理；请查询原任务或幂等重试，不能假定分析完成。'
            raise
        self.trace[-1]['status']='completed'
        self.state='WAIT_RESULT'
        self.trace.append({'stage':'result','label':'反诈任务受理','status':'waiting','detail':'任务已提交，等待领域模型分析；受理不是风险结论。'})
        return self.packet('反诈请求已受理，请 /status 查询；受理不等于检测完成。',domain='fraud',domainResult=result)


def main():
    session=DomainChat()
    print('A1学校模型自然语言领域联通（本机演练，非P2正式总调度）')
    print('输入需求，由学校模型追问或规划；旅游咨询/反诈文本可调用已有服务。')
    print('/status 查询；/retry 重试未确认提交；/new 新需求；/exit 退出。没有模型或服务时明确失败。')
    while True:
        try:
            text=input('老人：').strip()
            if text=='/exit':return
            if not text:continue
            print('处理中……',flush=True)
            print(json.dumps(session.send(text),ensure_ascii=False,indent=2))
        except (PlanningError,DomainError) as error:
            print('未假定成功：'+str(error))
        except (EOFError,KeyboardInterrupt):return


if __name__=='__main__':main()
