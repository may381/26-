import copy
import unittest
from unittest.mock import Mock
from local_domains import DomainClient, DomainError
from domain_chat import DomainChat
from test_domain_chat import plan


def response(state='completed'):
    return {'analysis_id':'real-test','status':state,'result':{
        'id':'real-test','level':'high','evidence':'原文要求先转账',
        'advice':['通过官方渠道核实']}}


class DomainResultTests(unittest.TestCase):
    def test_tourism_empty_and_wrong_results(self):
        for value in ({},None,[],{'text':''},{'text':'  '},{'text':[]},{'tools':[]}):
            with self.subTest(value=value):
                client=DomainClient(Mock(return_value={'code':'OK','data':value}))
                with self.assertRaises(DomainError): client.tourism('杭州旅游')

    def test_tourism_chat_does_not_reuse_old_result(self):
        p=plan('tourism');p['location']='杭州'
        client=Mock();client.tourism.side_effect=[{'text':'旧结果'},{}]
        chat=DomainChat(Mock(return_value=p),client)
        self.assertIn('domainResult',chat.send('杭州旅游'))
        packet=chat.send('多休息')
        self.assertNotIn('domainResult',packet)
        self.assertFalse(packet['executed'])
        self.assertEqual(packet['executionTrace'][-1]['status'],'failed')

    def test_completed_result_requires_valid_fields(self):
        cases=[None,{},[],{'id':'real-test'}]
        for field,bad in [('id','real-other'),('level','unknown'),('evidence',' '),
                          ('advice',[]),('advice',[None])]:
            value=response()['result'];value[field]=bad;cases.append(value)
        for result in cases:
            client=DomainClient(Mock(return_value={**response(),'result':result}))
            client.analysis_id='real-test'
            with self.subTest(result=result), self.assertRaises(DomainError):client.status()
            self.assertEqual(client.analysis_id,'real-test')

    def test_wrong_or_missing_identity_rejected(self):
        for identity in (None,'real-other',123):
            value=response();value['analysis_id']=identity
            client=DomainClient(Mock(return_value=value));client.analysis_id='real-test'
            with self.assertRaises(DomainError):client.status()

    def test_noncompleted_result_and_raw_error_are_removed(self):
        for state in ('queued','processing','failed','interrupted'):
            value=response(state);value['error']='SECRET'
            client=DomainClient(Mock(return_value=value));client.analysis_id='real-test'
            result=client.status()
            self.assertIsNone(result['result']);self.assertNotIn('SECRET',str(result))

    def test_status_failure_preserves_task_and_recovers_without_model(self):
        bad=response();bad['analysis_id']='real-other'
        transport=Mock(side_effect=[DomainError('SECRET'),bad,response()])
        client=DomainClient(transport);client.analysis_id='real-test'
        client.pending=None
        planner=Mock();chat=DomainChat(planner,client)
        chat.state='WAIT_RESULT';chat.inputs=['原始证据']
        chat.conversation.history=[{'role':'user','content':'原始证据'}]
        history=copy.deepcopy(chat.conversation.history)
        for _ in range(2):
            packet=chat.send('/status')
            self.assertEqual(packet['state'],'WAIT_RESULT')
            self.assertNotIn('domainResult',packet)
            self.assertNotIn('SECRET',str(packet))
            self.assertEqual(packet['executionTrace'][-1]['status'],'failed')
            self.assertEqual(client.analysis_id,'real-test')
            self.assertEqual(chat.conversation.history,history)
            self.assertEqual(chat.inputs,['原始证据'])
        packet=chat.send('/status')
        self.assertEqual(packet['state'],'COMPLETE')
        self.assertEqual(packet['domainResult'],response())
        self.assertEqual(packet['executionTrace'][-1]['status'],'completed')
        planner.assert_not_called()
        self.assertTrue(all(call.args==('GET','/api/analyses/real-test') for call in transport.call_args_list))


if __name__=='__main__':unittest.main()
