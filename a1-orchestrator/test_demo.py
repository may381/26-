import unittest
from unittest.mock import Mock
from demo import DemoSession


class DemoTests(unittest.TestCase):
    def setUp(self):
        self.plan = {"decision": "PLAN", "reply": "正在查找", "domains": ["culture"],
                     "steps": [{"id": "s1", "agent": "a3", "domain": "culture", "goal": "查课程", "dependsOn": []}],
                     "memoryCandidate": None, "location": "长沙"}
        self.model = Mock(return_value=self.plan)
        self.session = DemoSession(self.model)

    def start(self):
        return self.session.send("长沙想学剪纸，别太远，希望女儿陪同")

    def test_mock_workflow_preserves_care_even_if_model_omits_domain(self):
        result = self.start()
        self.assertIn("并非查到的真实课程", result)
        self.assertNotIn("正在查找", result)
        self.session.send("1")
        self.assertEqual(self.session.state, "WAIT_CONFIRMATION")
        self.assertEqual(len(self.session.gateway.effects), 0)
        self.session.send("同意")
        self.assertEqual(self.session.state, "COMPLETE")
        effect = next(iter(self.session.gateway.effects.values()))
        self.assertEqual(effect["notificationStatus"], "MOCK_NOT_SENT")
        self.assertFalse(self.session.snapshot()["realBusinessExecuted"])
        self.session.send("同意")
        self.assertEqual(len(self.session.gateway.effects), 1)
        self.assertEqual(self.model.call_count, 1)

    def test_reject_creates_no_effect(self):
        self.start()
        self.session.send("2")
        self.session.send("拒绝")
        self.assertFalse(self.session.gateway.effects)
        self.assertEqual(self.session.confirmation["state"], "REJECTED")

    def test_ambiguous_confirmation_does_not_execute(self):
        self.start()
        self.session.send("1")
        self.session.send("随便")
        self.assertEqual(self.session.state, "WAIT_CONFIRMATION")
        self.assertFalse(self.session.gateway.effects)

    def test_invalid_selection_does_not_call_care(self):
        self.start()
        before = len(self.session.gateway.events)
        self.session.send("99")
        self.assertEqual(len(self.session.gateway.events), before)
        self.assertEqual(self.session.state, "WAIT_SELECTION")

    def test_cancel_prevents_later_execution(self):
        self.start()
        self.session.send("1")
        self.session.send("/cancel")
        self.session.send("同意")
        self.assertFalse(self.session.gateway.effects)
        self.assertEqual(self.session.state, "CANCELLED")

    def test_location_question_before_demo_courses(self):
        self.model.return_value = dict(self.plan, location=None)
        self.assertIn("城市", self.session.send("想学剪纸，别太远，希望女儿陪同"))
        self.assertFalse(self.session.gateway.events)
        self.model.return_value = self.plan
        self.session.send("长沙")
        self.assertEqual(self.session.state, "WAIT_SELECTION")


if __name__ == "__main__":
    unittest.main()
