import unittest
from unittest.mock import Mock
from domain_chat import DomainChat
from test_domain_chat import plan
from local_domains import DomainClient, DomainError


class GraphRuntimeTests(unittest.TestCase):
    def test_real_graph_routes_tourism(self):
        value = plan('tourism'); value['location'] = '杭州'
        client = Mock(); client.tourism.return_value = {'text': 'fixture'}
        chat = DomainChat(Mock(return_value=value), client)
        updates = list(chat.graph.stream({'text': '杭州两天，少走路'}, stream_mode='updates'))
        self.assertEqual([next(iter(x)) for x in updates],
                         ['control', 'request', 'planning', 'validation', 'tourism'])
        client.tourism.assert_called_once_with('杭州两天，少走路')
        client.fraud.assert_not_called()

    def test_control_exits_without_planning(self):
        planner = Mock(); chat = DomainChat(planner, Mock())
        updates = list(chat.graph.stream({'text': '/overview'}, stream_mode='updates'))
        self.assertEqual([next(iter(x)) for x in updates], ['control', 'request'])
        planner.assert_not_called()

    def test_turn_channels_do_not_leak_previous_packet(self):
        planner = Mock(return_value=plan())
        client = Mock(); client.pending = None
        chat = DomainChat(planner, client)
        chat.send('/overview')
        self.assertEqual(chat.send('请分析可疑短信')['state'], 'WAIT_RESULT')
        planner.assert_called_once()

    def test_instances_keep_separate_evidence(self):
        a = DomainChat(Mock(return_value=plan(decision='ASK')), Mock())
        b = DomainChat(Mock(), Mock())
        a.send('我的原文')
        self.assertEqual(b.inputs, [])
        self.assertEqual(b.conversation.history, [])

    def test_status_has_own_node_and_preserves_evidence(self):
        for status, expected in [('queued', 'WAIT_RESULT'), ('processing', 'WAIT_RESULT'),
                                 ('completed', 'COMPLETE'), ('failed', 'FAILED'),
                                 ('interrupted', 'FAILED')]:
            with self.subTest(status=status):
                planner = Mock(); client = Mock()
                client.analysis_id = 'real-test'
                client.status.return_value = {'analysis_id': 'real-test', 'status': status, 'result': {'id':'real-test','level':'high','evidence':'依据','advice':['核实']} if status=='completed' else None}
                chat = DomainChat(planner, client); chat.inputs = ['原始证据']
                updates = list(chat.graph.stream({'text': ' /status '}, stream_mode='updates'))
                self.assertEqual([next(iter(x)) for x in updates], ['control', 'status'])
                self.assertEqual(updates[-1]['status']['packet']['state'], expected)
                self.assertEqual(chat.inputs, ['原始证据'])
                planner.assert_not_called(); client.fraud.assert_not_called()

    def test_reset_and_new_have_separate_nodes_and_only_clear_local(self):
        for command in ('new', 'reset'):
            with self.subTest(command=command):
                planner = Mock(); client = DomainClient(Mock())
                client.pending = ('原文', 'local-original')
                chat = DomainChat(planner, client)
                chat.state = 'SUBMISSION_UNCERTAIN'; chat.inputs = ['原文']
                chat.conversation.history = [{'role': 'user', 'content': '原文'}]
                updates = list(chat.graph.stream({'text': '/' + command}, stream_mode='updates'))
                self.assertEqual([next(iter(x)) for x in updates], ['control', command])
                packet = updates[-1][command]['packet']
                self.assertEqual(packet['state'], 'READY')
                self.assertEqual(packet['executionTrace'], [])
                self.assertIsNone(client.pending)
                self.assertEqual(chat.inputs, [])
                self.assertEqual(chat.conversation.history, [])
                client.transport.assert_not_called(); planner.assert_not_called()

    def test_retry_node_reuses_real_client_pending_and_trace(self):
        transport = Mock(side_effect=[DomainError('offline'), {'analysis_id': 'real-retry'}])
        client = DomainClient(transport); client.pending = ('原始完整文本', 'local-original')
        planner = Mock(); chat = DomainChat(planner, client)
        chat.state = 'SUBMISSION_UNCERTAIN'
        failed = chat.send('/retry')
        self.assertEqual(failed['state'], 'SUBMISSION_UNCERTAIN')
        self.assertEqual(client.pending, ('原始完整文本', 'local-original'))
        updates = list(chat.graph.stream({'text': '/retry'}, stream_mode='updates'))
        self.assertEqual([next(iter(x)) for x in updates], ['control', 'retry'])
        packet = updates[-1]['retry']['packet']
        self.assertEqual(packet['state'], 'WAIT_RESULT')
        self.assertEqual([x['stage'] for x in packet['executionTrace'][-2:]], ['retry', 'result'])
        self.assertEqual([x['status'] for x in packet['executionTrace'][-2:]], ['completed', 'waiting'])
        self.assertEqual(transport.call_args_list[0], transport.call_args_list[1])
        self.assertEqual(transport.call_args.args[2]['text'], '原始完整文本')
        self.assertEqual(transport.call_args.args[3]['Idempotency-Key'], 'local-original')
        planner.assert_not_called()

    def test_retry_without_pending_never_submits(self):
        client = DomainClient(Mock()); planner = Mock()
        chat = DomainChat(planner, client)
        packet = chat.send('/retry')
        self.assertIn('不会新建任务', packet['reply'])
        client.transport.assert_not_called(); planner.assert_not_called()

    def test_status_failure_returns_compatible_packet_without_changing_task(self):
        client = DomainClient(Mock(side_effect=DomainError('private error')))
        client.analysis_id = 'real-original'
        chat = DomainChat(Mock(), client); chat.state = 'WAIT_RESULT'
        packet = chat.send('/status')
        self.assertEqual(packet['state'], 'WAIT_RESULT')
        self.assertFalse(packet['executed'])
        self.assertFalse(packet['notificationExecuted'])
        self.assertFalse(packet['sharedMemoryWritten'])
        self.assertEqual(packet['executionTrace'][-1]['stage'], 'result')
        self.assertNotIn('private error', str(packet))
        self.assertEqual(client.analysis_id, 'real-original')
