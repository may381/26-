"""锁定 LangGraph 的图形状：加节点/改边必须同步改这里，避免图悄悄漂移。"""
import unittest

from domain_chat import DomainChat
from graph_runtime import DONE, NODE_NAMES, ROUTES, mermaid, topology


class TopologyTests(unittest.TestCase):
    def setUp(self):
        self.app = DomainChat().graph
        self.nodes, self.branches = topology(self.app)
        self.visible = {n for n in self.nodes if not n.startswith("__")}

    def test_node_set_is_exactly_the_declared_ten(self):
        self.assertEqual(self.visible, set(NODE_NAMES))

    def test_branch_targets_match_route_contract(self):
        for source, allowed in ROUTES.items():
            actual = {t for t in self.branches.get(source, set()) if not t.startswith("__")}
            self.assertEqual(actual, set(allowed), "%s 的分叉与契约不一致" % source)

    def test_only_three_nodes_branch(self):
        self.assertEqual(set(self.branches), set(ROUTES))

    def test_every_node_reaches_end(self):
        # 从每个节点出发都能走到 END，防止加了节点却忘了连边。
        graph = self.app.get_graph()
        edges = {}
        for edge in graph.edges:
            edges.setdefault(edge.source, set()).add(edge.target)
        for node in sorted(self.visible):
            seen, stack = set(), [node]
            while stack:
                current = stack.pop()
                if current == "__end__":
                    break
                for nxt in edges.get(current, ()):
                    if nxt not in seen:
                        seen.add(nxt)
                        stack.append(nxt)
            else:
                self.fail("节点 %s 走不到 END" % node)

    def test_mermaid_contains_every_node(self):
        text = mermaid(self.app)
        for node in NODE_NAMES:
            self.assertIn(node, text)
        self.assertIn("graph TD", text)

    def test_validation_branches_are_done_tourism_fraud(self):
        self.assertEqual({t for t in self.branches["validation"] if t != "__end__"},
                         {"tourism", "fraud"})


if __name__ == "__main__":
    unittest.main()
