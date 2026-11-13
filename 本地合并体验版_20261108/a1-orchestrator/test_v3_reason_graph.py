import unittest

from v3_reason_graph import REASONS, REASON_GRAPH, route_reason


class V3ReasonGraphTests(unittest.TestCase):
    def test_every_frozen_reason_has_its_own_graph_node(self):
        nodes = set(REASON_GRAPH.get_graph().nodes)
        self.assertIn("choose", nodes)
        for reason in REASONS:
            self.assertIn(reason.lower(), nodes)
            self.assertEqual(route_reason(reason), reason)

    def test_unknown_reason_is_rejected_before_graph_execution(self):
        with self.assertRaises(ValueError):
            route_reason("RETRY_EVERYTHING")

    def test_invocations_do_not_leak_previous_branch(self):
        for reason in reversed(REASONS):
            self.assertEqual(route_reason(reason), reason)


if __name__ == "__main__":
    unittest.main()
