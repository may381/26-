import unittest
from unittest.mock import Mock
from local_domains import DomainClient, DomainError, validate_analysis_status
from domain_chat import DomainChat
from test_domain_results import response
from test_domain_chat import plan


class ResultTrustTests(unittest.TestCase):
    def test_demo_rejected_at_client_and_chat(self):
        for text in ('清风园演示资料','清风园演示数据','演示园区的记录','尚未选中真实地点'):
            transport=Mock(return_value={'code':'OK','data':{'text':text}})
            with self.assertRaises(DomainError):DomainClient(transport).tourism('杭州')
            client=Mock();client.tourism.return_value={'text':text}
            p=plan('tourism');p['location']='杭州'
            packet=DomainChat(Mock(return_value=p),client).send('杭州旅游')
            self.assertNotIn('domainResult',packet)
            self.assertFalse(packet['executed'])

    def test_mock_source_is_rejected_even_without_demo_wording(self):
        data={'text':'已找到三条路线','tools':[{'tool':'route.recommend',
              'result':{'source':'MOCK','routes':[]}}]}
        transport=Mock(return_value={'code':'OK','data':data})
        with self.assertRaises(DomainError):
            DomainClient(transport).tourism('规划路线')

    def test_real_source_is_not_rejected(self):
        data={'text':'已找到橘子洲','tools':[{'tool':'place.search',
              'result':{'source':'AMAP','places':[]}}]}
        transport=Mock(return_value={'code':'OK','data':data})
        self.assertEqual(DomainClient(transport).tourism('查询橘子洲'),data)

    def test_trusted_location_sent_using_existing_context(self):
        transport=Mock(return_value={'code':'OK','data':{'text':'杭州旅游咨询资料'}})
        p=plan('tourism');p['location']='杭州'
        packet=DomainChat(Mock(return_value=p),DomainClient(transport)).send('杭州旅游')
        body=transport.call_args.args[2]
        self.assertEqual(body['context'],{'location':'杭州'})
        self.assertEqual(body['text'],'杭州旅游')
        self.assertIn('domainResult',packet)
        with self.assertRaises(DomainError):DomainClient(transport).tourism('杭州','上海')

    def test_unverified_history_preserves_task_and_can_recover(self):
        bad=response();bad['result']['evidence']='结合用户近期多次遭遇诈骗，风险极高'
        transport=Mock(side_effect=[bad,response()])
        client=DomainClient(transport);client.analysis_id='real-test';client.analysis_text='原文要求先转账'
        chat=DomainChat(Mock(),client);chat.state='WAIT_RESULT'
        chat.task_domain='fraud';chat.inputs=['原文要求先转账']
        packet=chat.send('/status')
        self.assertNotIn('domainResult',packet)
        self.assertEqual(chat.state,'WAIT_RESULT')
        self.assertEqual(client.analysis_id,'real-test')
        packet=chat.send('/status')
        self.assertEqual(packet['state'],'COMPLETE')
        self.assertEqual(packet['executionTrace'][-1]['label'],'接收反诈分析结果')

    def test_excerpt_offsets_and_public_sources_are_not_user_history(self):
        value=response();value['result']['evidenceItems']=[{'excerpt':'转账','start':0,'end':2}]
        with self.assertRaises(DomainError):validate_analysis_status(value,'real-test','要求转账')
        value['result']['evidenceItems'][0].update(start=2,end=4)
        validate_analysis_status(value,'real-test','要求转账')
        value['result']['evidence']='用户此前多次遭遇退款诈骗'
        value['result']['sources']=[{'source':'https://example.com/case'}]
        with self.assertRaises(DomainError):validate_analysis_status(value,'real-test','要求转账')

    def test_generic_recent_fraud_trend_is_not_user_history(self):
        value=response()
        value['result']['evidence']='近期快递退款诈骗较常见，要求验证码具有高风险'
        validate_analysis_status(value,'real-test','客服要求点击链接并提供验证码')


if __name__=='__main__':unittest.main()
