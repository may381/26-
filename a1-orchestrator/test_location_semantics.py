"""Semantic location gates use user evidence, never the planner's assertion."""
import copy
import unittest
from unittest.mock import Mock

from a1 import enforce_location
from domain_chat import DomainChat
from test_conversation import travel


class LocationSemanticTests(unittest.TestCase):
    def check_blocked(self, text, location, history=None):
        original = travel(location)
        before = copy.deepcopy(original)
        result = enforce_location(original, text, history)
        self.assertEqual(result['decision'], 'ASK')
        self.assertEqual(result['steps'], [])
        self.assertIsNone(result['location'])
        self.assertEqual(original, before)
        client = Mock()
        chat = DomainChat(Mock(return_value=original), client)
        if history:
            chat.conversation.history = copy.deepcopy(history)
        packet = chat.send(text)
        self.assertFalse(packet.get('executed', False))
        client.tourism.assert_not_called()
        client.fraud.assert_not_called()
        self.assertNotIn('dispatch', [x['stage'] for x in packet['executionTrace']])

    def test_negated_locations(self):
        for text in ('不去上海，想出去玩', '不想去上海旅游', '目的地不是上海',
                     '上海先不去', '排除上海旅游'):
            with self.subTest(text=text):
                self.check_blocked(text, '上海')

    def test_negation_overrides_historical_destination(self):
        self.check_blocked('不去杭州了', '杭州',
                           [{'role': 'user', 'content': '杭州旅游，少走路'}])

    def test_changed_destination_overrides_old(self):
        history = [{'role': 'user', 'content': '想去杭州旅游，少走路，多休息'}]
        for text in ('改去苏州，两天', '目的地改成苏州', '现在去苏州', '去苏州'):
            with self.subTest(text=text):
                self.check_blocked(text, '杭州', history)
                self.assertEqual(enforce_location(travel('苏州'), text, history)['decision'], 'PLAN')

    def test_changed_destination_same_turn(self):
        self.check_blocked('原计划去杭州，现在改去苏州', '杭州')
        self.assertEqual(enforce_location(travel('苏州'), '原计划去杭州，现在改去苏州')['decision'], 'PLAN')

    def test_third_party_is_not_user_choice(self):
        for text in ('朋友推荐上海旅游', '听说上海很好玩', '家人建议去上海'):
            with self.subTest(text=text):
                self.check_blocked(text, '上海')

    def test_recommendation_with_explicit_user_choice(self):
        text = '朋友推荐上海，但我想去杭州旅游'
        self.check_blocked(text, '上海')
        self.assertEqual(enforce_location(travel('杭州'), text)['decision'], 'PLAN')

    def test_departure_is_not_destination(self):
        for text in ('从深圳去杭州旅游', '从深圳出发，去杭州旅游', '出发地是深圳，目的地是杭州'):
            with self.subTest(text=text):
                self.check_blocked(text, '深圳')
                self.assertEqual(enforce_location(travel('杭州'), text)['decision'], 'PLAN')

    def test_departure_only_does_not_supply_destination(self):
        self.check_blocked('从深圳出发，想出去玩', '深圳')

    def test_uncertain_destination_does_not_reuse_old(self):
        history = [{'role': 'user', 'content': '杭州旅游'}]
        self.check_blocked('目的地还没确定', '杭州', history)
        self.check_blocked('杭州还是苏州，我没决定', '杭州', history)

    def test_same_task_constraints_survive_correction(self):
        client = Mock()
        client.tourism.return_value = {'text': '旅游咨询结果'}
        planner = Mock(side_effect=[travel('杭州'), travel('杭州'), travel('苏州')])
        chat = DomainChat(planner, client)
        first = '想去杭州旅游，少走路，多休息'
        chat.send(first)
        client.tourism.reset_mock()
        correction = '改去苏州，两天'
        chat.send(correction)
        client.tourism.assert_not_called()
        chat.send('苏州，预算没确定')
        client.tourism.assert_called_once_with(first + '\n' + correction + '\n苏州，预算没确定')


if __name__ == '__main__':
    unittest.main()
