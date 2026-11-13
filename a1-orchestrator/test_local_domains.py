import unittest
from unittest.mock import Mock
from local_domains import DomainClient,DomainError


class LocalDomainTests(unittest.TestCase):
    def test_retry_uses_original_idempotency_key(self):
        transport=Mock(side_effect=[DomainError('disconnected'),{'analysis_id':'real-demo'}])
        client=DomainClient(transport)
        with self.assertRaises(DomainError):client.fraud('可疑测试文本')
        client.fraud('',retry=True)
        self.assertEqual(transport.call_args_list[0],transport.call_args_list[1])
        self.assertIsNone(client.pending)
        with self.assertRaises(DomainError):client.fraud('重复请求')

    def test_tourism_preserves_server_evidence(self):
        value={'text':'回答','tools':[{'source':'AMAP','retrievedAt':'2026-11-07T08:56:02Z'}]}
        client=DomainClient(Mock(return_value={'code':'OK','data':value}))
        self.assertEqual(client.tourism('你好'),value)

    def test_false_completed_result_rejected(self):
        client=DomainClient(Mock(return_value={'status':'completed','result':None}))
        client.analysis_id='real-test'
        with self.assertRaises(DomainError):client.status()

    def test_uncertain_submission_cannot_be_overwritten(self):
        transport=Mock(side_effect=DomainError('unknown outcome'))
        client=DomainClient(transport)
        with self.assertRaises(DomainError):client.fraud('原始需求')
        original=client.pending
        with self.assertRaises(DomainError):client.fraud('另一个需求')
        self.assertEqual(client.pending,original)
        self.assertEqual(transport.call_count,1)
        client.new()
        self.assertIsNone(client.pending)
        with self.assertRaises(DomainError):client.fraud('',retry=True)

    def test_unknown_status_is_not_success(self):
        for response in [[],{}, {'status':'success','result':{}}]:
            client=DomainClient(Mock(return_value=response))
            client.analysis_id='real-test'
            with self.assertRaises(DomainError):client.status()

    def test_empty_tourism_never_sent(self):
        transport=Mock()
        with self.assertRaises(DomainError):DomainClient(transport).tourism('   ')
        transport.assert_not_called()

    def test_places_keep_only_real_amap_points_with_coordinates(self):
        transport=Mock(return_value={'code':'OK','data':{'source':'AMAP','places':[
            {'name':'西湖','address':'杭州市西湖区','location':'120.155,30.265','type':'风景名胜'},
            {'name':'无坐标地点','location':'not-a-point'},
            {'name':'   ','location':'120.1,30.1'},
            'bad-item']}})
        places=DomainClient(transport).places('西湖','杭州')
        self.assertEqual([place['name'] for place in places],['西湖'])
        self.assertEqual(places[0]['location'],'120.155,30.265')

    def test_places_reject_non_amap_source(self):
        client=DomainClient(Mock(return_value={'code':'OK','data':{'source':'MOCK','places':[]}}))
        with self.assertRaises(DomainError):client.places('西湖')

    def test_places_reject_blank_query_without_calling_upstream(self):
        transport=Mock()
        with self.assertRaises(DomainError):DomainClient(transport).places('  ')
        transport.assert_not_called()
