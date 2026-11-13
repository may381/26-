import unittest
from unittest.mock import Mock
from mock_flow import Flow


class FlowTests(unittest.TestCase):
    def flow(self):
        ask = dict(decision='ASK', reply='哪个城市？', domains=['culture'], steps=[], memoryCandidate=None)
        plan = dict(decision='PLAN', reply='计划', domains=['culture'], memoryCandidate=None,
                    location='长沙', steps=[dict(id='s1', agent='a3', domain='culture', goal='课程', dependsOn=[])])
        return Flow(Mock(side_effect=[ask, plan]))

    def send(self, flow, rid, text):
        return flow.handle(dict(sessionId='session', requestId=rid, text=text))

    def test_full_restore_approve_and_duplicate(self):
        flow = self.flow()
        self.send(flow, '1', '想学剪纸，别太远，希望女儿陪同')
        result = self.send(flow, '2', '长沙')
        self.assertEqual(result['snapshot']['state'], 'WAIT_SELECTION')
        self.assertIn('女儿陪同', flow.planner.call_args.args[1][0]['content'])
        self.send(flow, '3', '1')
        result = self.send(flow, '4', '同意')
        self.assertEqual(result, self.send(flow, '4', '同意'))
        self.send(flow, '5', '同意')
        self.assertEqual(len(flow.sessions['session'].gateway.effects), 1)
        self.assertFalse(result['snapshot']['realBusinessExecuted'])

    def test_reject_and_cancel(self):
        for decision in ('拒绝', '/cancel'):
            flow = self.flow()
            self.send(flow, '1', '想学剪纸，女儿陪同')
            self.send(flow, '2', '长沙')
            self.send(flow, '3', '1')
            self.send(flow, '4', decision)
            self.send(flow, '5', '同意')
            self.assertFalse(flow.sessions['session'].gateway.effects)

    def test_request_conflict(self):
        flow = self.flow()
        self.send(flow, '1', '想学剪纸')
        with self.assertRaises(ValueError):
            self.send(flow, '1', '其他需求')
