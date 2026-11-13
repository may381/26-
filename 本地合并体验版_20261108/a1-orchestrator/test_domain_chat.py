import unittest
from unittest.mock import Mock
from domain_chat import DomainChat
from local_domains import DomainError


def plan(domain='fraud',decision='PLAN'):
    return {'decision':decision,'reply':'请提供原文','domains':[domain],
            'steps':[{'id':'s1','agent':'a1' if domain in ('fraud','tourism') else 'a3','domain':domain,
                      'goal':'模型改写的目标不得作为证据','dependsOn':[]}] if decision=='PLAN' else [],
            'memoryCandidate':None,'location':None}


class DomainChatTests(unittest.TestCase):
    def test_failed_tourism_dispatch_is_not_marked_successful(self):
        client=Mock();client.tourism.side_effect=DomainError('offline')
        value=plan('tourism');value['location']='杭州'
        session=DomainChat(Mock(return_value=value),client)
        self.assertFalse(session.send('杭州旅游')['executed'])
        self.assertEqual(session.trace[-1]['stage'],'dispatch')
        self.assertEqual(session.trace[-1]['status'],'failed')

    def test_uncertain_dispatch_is_not_marked_successful(self):
        client=Mock();client.fraud.side_effect=DomainError('timeout')
        session=DomainChat(Mock(return_value=plan()),client)
        self.assertFalse(session.send('合成原文')['executed'])
        self.assertEqual(session.trace[-1]['status'],'uncertain')

    def test_execution_trace_reflects_real_dispatch_without_internal_thoughts(self):
        client=Mock();client.fraud.return_value={'analysisId':'fixture'}
        session=DomainChat(Mock(return_value=plan()),client)
        result=session.send('合成可疑原文')
        self.assertEqual([x['stage'] for x in result['executionTrace']],['received','planning','validation','dispatch','result'])
        self.assertEqual(result['executionTrace'][-1]['status'],'waiting')
        self.assertNotIn('合成可疑原文',str(result['executionTrace']))
        session.send('/new');self.assertEqual(session.trace,[])

    def test_completed_fraud_can_start_new_tourism_without_old_evidence(self):
        client=Mock();value=plan('tourism');value['location']='杭州'
        session=DomainChat(Mock(return_value=value),client)
        session.state='COMPLETE';session.inputs=['旧的可疑短信']
        session.send('去杭州旅游')
        client.new.assert_called_once()
        client.tourism.assert_called_once_with('去杭州旅游')

    def test_invalid_input_does_not_consume_model_or_dispatch(self):
        planner=Mock();client=Mock();session=DomainChat(planner,client)
        for value in (None, '', '   ', 'x'*10001):
            self.assertFalse(session.send(value)['executed'])
        planner.assert_not_called();client.fraud.assert_not_called();client.tourism.assert_not_called()

    def test_overview_does_not_consume_model_or_drop_task(self):
        planner=Mock();client=Mock();client.analysis_id='real-test';session=DomainChat(planner,client)
        session.state='WAIT_RESULT'
        result=session.send('/overview')
        self.assertEqual(result['analysisId'],'real-test');self.assertEqual(result['state'],'WAIT_RESULT')
        planner.assert_not_called();client.new.assert_not_called()

    def test_unknown_control_never_consumes_model_call(self):
        planner=Mock();session=DomainChat(planner,Mock())
        session.send('/unknown');planner.assert_not_called()

    def test_tourism_city_answer_keeps_original_constraints(self):
        client=Mock();value=plan('tourism');value['location']='长沙'
        session=DomainChat(Mock(side_effect=[plan('tourism','ASK'),value]),client)
        session.send('想去旅游，少走路，希望女儿陪同')
        client.tourism.assert_not_called()
        session.send('长沙')
        client.tourism.assert_called_once_with('想去旅游，少走路，希望女儿陪同\n长沙')

    def test_clarification_then_fraud_preserves_user_evidence(self):
        client=Mock();client.fraud.return_value={'analysisId':'real-test'}
        session=DomainChat(Mock(side_effect=[plan(decision='ASK'),plan()]),client)
        session.send('帮我判断短信风险')
        client.fraud.assert_not_called()
        result=session.send('要求转入安全账户')
        client.fraud.assert_called_once_with('帮我判断短信风险\n要求转入安全账户')
        self.assertEqual(result['state'],'WAIT_RESULT')
        self.assertNotIn('模型改写',client.fraud.call_args[0][0])
        session.send('重复需求')
        self.assertEqual(client.fraud.call_count,1)

    def test_unavailable_agent_or_multi_step_never_partially_dispatches(self):
        for value in (plan('culture'),{**plan(),'steps':plan()['steps']+[{**plan()['steps'][0],'id':'s2','dependsOn':['s1']}]}):
            client=Mock();session=DomainChat(Mock(return_value=value),client)
            self.assertFalse(session.send('请求处理')['executed'])
            client.fraud.assert_not_called();client.tourism.assert_not_called()

    def test_uncertain_submission_retries_without_replanning(self):
        client=Mock();client.fraud.side_effect=[DomainError('disconnected'),{'analysisId':'real-test'}]
        planner=Mock(return_value=plan());session=DomainChat(planner,client)
        self.assertFalse(session.send('合成短信')['executed'])
        self.assertEqual(session.state,'SUBMISSION_UNCERTAIN')
        retry=session.send('/retry')
        client.fraud.assert_called_with('',retry=True);self.assertEqual(planner.call_count,1)
        self.assertEqual([item['stage'] for item in retry['executionTrace']][-2:],['retry','result'])
        self.assertEqual(retry['executionTrace'][-2]['status'],'completed')
        self.assertEqual(retry['executionTrace'][-1]['status'],'waiting')

    def test_status_and_new_do_not_fabricate_remote_cancellation(self):
        client=Mock();client.analysis_id='real-test';client.status.return_value={'analysis_id':'real-test','status':'interrupted','result':None}
        session=DomainChat(client=client)
        self.assertEqual(session.send('/status')['state'],'FAILED')
        result=session.send('/new');self.assertEqual(result['state'],'READY')
        self.assertIn('不会取消',result['reply']);client.new.assert_called_once()


class AdditionalDomainChatTests(unittest.TestCase):
    def test_failure_packet_has_safe_reply_and_trace(self):
        from a1 import PlanningError
        planner=Mock(side_effect=PlanningError('SECRET upstream'))
        session=DomainChat(planner,Mock())
        packet=session.send('test')
        self.assertEqual(packet['executionTrace'][-1]['stage'],'planning')
        self.assertEqual(packet['executionTrace'][-1]['status'],'failed')
        self.assertNotIn('SECRET',str(packet))
        self.assertFalse(packet['notificationExecuted'])
        self.assertFalse(packet['sharedMemoryWritten'])
        self.assertEqual(session.conversation.history,[])
        client=Mock();client.status.side_effect=DomainError('SECRET')
        session=DomainChat(client=client);session.state='WAIT_RESULT'
        packet=session.send('/status')
        self.assertEqual(packet['state'],'WAIT_RESULT')
        self.assertEqual(packet['executionTrace'][-1]['stage'],'result')
        self.assertNotIn('SECRET',str(packet))

    def test_retry_without_pending_never_creates_task(self):
        client=Mock();client.pending=None
        planner=Mock();session=DomainChat(planner,client)
        packet=session.send('/retry')
        self.assertIn('不会新建任务',packet['reply'])
        self.assertEqual(packet['state'],'READY')
        self.assertEqual(packet['executionTrace'],[])
        planner.assert_not_called();client.fraud.assert_not_called()

    def test_retry_reuses_real_client_pending_on_failure_and_success(self):
        from local_domains import DomainClient
        transport=Mock(side_effect=[DomainError('offline'),DomainError('offline'),
                                    {'analysis_id':'real-retry'}])
        client=DomainClient(transport)
        planner=Mock(return_value=plan())
        session=DomainChat(planner,client)
        self.assertFalse(session.send('original evidence')['executed'])
        pending=client.pending
        self.assertFalse(session.send('/retry')['executed'])
        self.assertEqual(session.state,'SUBMISSION_UNCERTAIN')
        self.assertEqual(client.pending,pending)
        self.assertEqual(session.trace[-1]['stage'],'retry')
        self.assertEqual(session.trace[-1]['status'],'uncertain')
        packet=session.send('/retry')
        self.assertEqual(packet['state'],'WAIT_RESULT')
        self.assertEqual([x['stage'] for x in packet['executionTrace']][-2:],['retry','result'])
        self.assertEqual([x['status'] for x in packet['executionTrace']][-2:],['completed','waiting'])
        self.assertEqual(packet['executionTrace'][-2]['label'],'复用原幂等键重试')
        self.assertEqual(transport.call_count,3)
        self.assertTrue(all(call==transport.call_args_list[0] for call in transport.call_args_list))
        self.assertEqual(planner.call_count,1)
        self.assertIsNone(client.pending)

    def test_full_fraud_limit_and_no_truncation(self):
        client=Mock();client.fraud.return_value={}
        session=DomainChat(Mock(return_value=plan()),client)
        text='x'*10000
        self.assertEqual(session.send(text)['state'],'WAIT_RESULT')
        client.fraud.assert_called_once_with(text)

    def test_tourism_cumulative_limit_never_dispatches(self):
        client=Mock()
        value=plan('tourism');value['location']='杭州'
        session=DomainChat(Mock(return_value=value),client)
        result=session.send('杭州'+ 'x'*1999)
        self.assertFalse(result['executed'])
        client.tourism.assert_not_called()
        self.assertEqual(result['executionTrace'][-1]['stage'],'validation')
        self.assertEqual(result['executionTrace'][-1]['status'],'failed')

    def test_pending_blocks_new_tasks_and_packet_is_snapshot(self):
        for state in ('WAIT_RESULT','SUBMISSION_UNCERTAIN'):
            client=Mock();planner=Mock()
            session=DomainChat(planner,client);session.state=state
            for text in ('new request','/image file.png','/unknown'):
                result=session.send(text)
                self.assertEqual(result['state'],state)
                self.assertFalse(result['notificationExecuted'])
                self.assertFalse(result['sharedMemoryWritten'])
            planner.assert_not_called();client.fraud.assert_not_called()
            client.tourism.assert_not_called();client.image.assert_not_called()
        session.trace=[{'stage':'received','status':'completed'}]
        result=session.packet('test')
        result['executionTrace'][0]['status']='changed'
        self.assertEqual(session.trace[0]['status'],'completed')

    def test_reset_and_poll_states(self):
        client=Mock();session=DomainChat(client=client)
        for remote,local in [('queued','WAIT_RESULT'),('processing','WAIT_RESULT'),
                             ('completed','COMPLETE'),('failed','FAILED'),('interrupted','FAILED')]:
            client.analysis_id='real-test';client.status.return_value={'analysis_id':'real-test','status':remote,'result':{'id':'real-test','level':'high','evidence':'依据','advice':['核实']} if remote=='completed' else None}
            self.assertEqual(session.send('/status')['state'],local)
            self.assertEqual(session.trace[-1]['stage'],'result')
        self.assertEqual(session.send('/reset')['state'],'READY')
        self.assertEqual(session.inputs,[])
        self.assertEqual(session.conversation.history,[])


if __name__=='__main__':unittest.main()
