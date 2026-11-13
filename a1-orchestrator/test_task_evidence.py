import copy
import unittest
from unittest.mock import Mock
from a1 import PlanningError
from domain_chat import DomainChat
from local_domains import DomainClient, DomainError
from test_domain_chat import plan


def travel(decision='PLAN'):
    return {**plan('tourism', decision), 'location': '杭州' if decision == 'PLAN' else None}


def snapshot(chat):
    return copy.deepcopy((chat.conversation.history, chat.conversation.last_plan,
                          chat.inputs, chat.task_domain, chat.state))


class TaskEvidenceTests(unittest.TestCase):
    def test_same_domain_clarification_preserves_constraints(self):
        client = Mock()
        chat = DomainChat(Mock(side_effect=[travel('ASK'), travel()]), client)
        chat.send('想出去玩，少走路，多休息')
        chat.send('杭州，两天')
        client.tourism.assert_called_once_with('想出去玩，少走路，多休息\n杭州，两天')
        self.assertEqual(chat.task_domain, 'tourism')

    def test_tourism_to_fraud_sends_only_new_evidence(self):
        planner = Mock(side_effect=[travel(), plan(), plan()])
        client = Mock(); chat = DomainChat(planner, client)
        chat.send('杭州两天，少走路')
        text = '这条短信要求我先转账再退款，帮我分析'
        chat.send(text)
        client.fraud.assert_called_once_with(text)
        self.assertEqual(planner.call_args.args[1], [])
        self.assertEqual(chat.inputs, [text])
        self.assertEqual(chat.task_domain, 'fraud')
        self.assertEqual([x['content'] for x in chat.conversation.history if x['role']=='user'], [text])

    def test_general_reply_is_not_domain_evidence(self):
        reply = {'decision':'REPLY', 'reply':'您好', 'domains':[], 'steps':[],
                 'memoryCandidate':None, 'location':None}
        client = Mock(); chat = DomainChat(Mock(side_effect=[reply, travel()]), client)
        chat.send('你好，我刚才吃了午饭')
        chat.send('杭州旅游')
        client.tourism.assert_called_once_with('杭州旅游')
        self.assertEqual(len(chat.conversation.history), 4)

    def test_waiting_and_uncertain_block_without_mutation(self):
        for state in ('WAIT_RESULT', 'SUBMISSION_UNCERTAIN'):
            with self.subTest(state=state):
                client = DomainClient(Mock()); client.pending=('原证据','local-original')
                planner=Mock(); chat=DomainChat(planner,client)
                chat.state=state; chat.task_domain='fraud'; chat.inputs=['原证据']
                before=snapshot(chat)
                chat.send('去杭州旅游')
                self.assertEqual(snapshot(chat), before)
                self.assertEqual(client.pending, ('原证据','local-original'))
                planner.assert_not_called(); client.transport.assert_not_called()

    def test_terminal_new_task_commits_only_after_valid_plan(self):
        for state in ('COMPLETE','FAILED'):
            with self.subTest(state=state):
                planner=Mock(side_effect=[PlanningError('offline'), travel()])
                client=Mock(); chat=DomainChat(planner,client)
                chat.state=state; chat.task_domain='fraud'; chat.inputs=['旧短信']
                chat.conversation.history=[{'role':'user','content':'旧短信'}]
                before=snapshot(chat)
                chat.send('杭州旅游')
                self.assertEqual(snapshot(chat),before)
                client.new.assert_not_called()
                chat.send('杭州旅游')
                client.new.assert_called_once()
                client.tourism.assert_called_once_with('杭州旅游')
                self.assertEqual(chat.inputs,['杭州旅游'])
                self.assertEqual(planner.call_args.args[1],[])

    def test_failed_switch_replanning_keeps_old_scope(self):
        planner=Mock(side_effect=[travel(), plan(), PlanningError('offline')])
        client=Mock(); chat=DomainChat(planner,client)
        chat.send('杭州两天'); before=snapshot(chat)
        chat.send('分析这条退款短信')
        self.assertEqual(snapshot(chat),before)
        client.fraud.assert_not_called(); client.new.assert_not_called()

    def test_invalid_structure_and_execution_rejection_do_not_commit(self):
        bad={**plan(), 'extra':'invalid'}
        multi={**plan(), 'steps':[plan()['steps'][0],{**plan()['steps'][0],'id':'s2'}]}
        for candidate in (bad,multi,travel()):
            with self.subTest(candidate=candidate):
                planner=Mock(side_effect=[travel(),candidate])
                client=Mock(); chat=DomainChat(planner,client)
                chat.send('杭州旅游'); before=snapshot(chat)
                # For travel(), trigger the 2000-character evidence gate.
                text='杭州'+'x'*1999 if candidate==travel() else '请继续'
                chat.send(text)
                self.assertEqual(snapshot(chat),before)
                self.assertEqual(client.tourism.call_count,1)
                client.fraud.assert_not_called()

    def test_uncertain_retry_keeps_isolated_original_text_and_key(self):
        transport=Mock(side_effect=[DomainError('offline'),{'analysis_id':'real-retry'}])
        client=DomainClient(transport)
        planner=Mock(side_effect=[travel('ASK'),plan(),plan()])
        chat=DomainChat(planner,client)
        chat.send('想去杭州旅游')
        text='短信要求提供验证码，请分析'
        chat.send(text)
        pending=client.pending
        self.assertEqual(pending[0],text)
        chat.send('/retry')
        self.assertEqual(transport.call_args_list[0],transport.call_args_list[1])
        self.assertEqual(chat.inputs,[text])
        self.assertEqual(chat.state,'WAIT_RESULT')
