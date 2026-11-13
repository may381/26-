import unittest

from dependency_integration import integrate_dependencies, collect_child_confirmations
from p2_client import P2Error


def child(task, domain, status="SUCCEEDED", required=True, text="完成", results=None, error=None):
    return {"taskId": task, "parentTaskId": "root", "targetAgent": "a3", "domain": domain,
            "required": required, "version": 2, "status": status,
            "reply": {"text": text, "speechRate": .8, "audioUrl": None},
            "results": results or [], "confirmationIds": [], "effectIds": [],
            "error": error, "completedAt": "2026-11-07T00:00:00Z", "inputRequest": None}


class DependencyIntegrationTests(unittest.TestCase):
    def test_all_success_preserves_cards(self):
        card={"resultId":"r1","type":"CULTURE","payload":{}}
        value=integrate_dependencies("root",[child("c1","culture",results=[card]),child("c2","care")])
        self.assertEqual(value["outcome"],"SUCCEEDED")
        self.assertEqual(value["results"],[card])
        self.assertEqual(value["domains"],["culture","care"])

    def test_success_and_failure_is_partial_and_explains_failure(self):
        value=integrate_dependencies("root",[
            child("c1","culture"),
            child("c2","care","FAILED",error={"code":"NO_SERVICE","message":"暂无陪同","retryable":False})])
        self.assertEqual(value["outcome"],"PARTIALLY_SUCCEEDED")
        self.assertIn("暂无陪同",value["reply"])

    def test_only_failures_is_failed(self):
        value=integrate_dependencies("root",[child("c1","culture","FAILED")])
        self.assertEqual(value["outcome"],"FAILED")

    def test_rejects_wrong_parent_or_nonterminal_snapshot(self):
        wrong=child("c1","culture");wrong["parentTaskId"]="other"
        running=child("c2","care");running["status"]="RUNNING"
        for item in (wrong,running):
            with self.assertRaises(P2Error):integrate_dependencies("root",[item])

    def test_accepts_p2_snapshot_without_parent_or_domain(self):
        # P2 的 AgentDelegationService.results() 只下发 taskId/targetAgent/required/
        # status/reply/results/error，快照归属由 P2 按根任务过滤。
        item={"taskId":"c1","targetAgent":"a2","required":True,"status":"FAILED",
              "reply":None,"results":[],
              "error":{"code":"INVOCATION_UNRESOLVED","message":"调用结果未确认","retryable":False}}
        value=integrate_dependencies("root",[item])
        self.assertEqual(value["outcome"],"FAILED")
        self.assertIn("调用结果未确认",value["reply"])
        self.assertEqual(value["domains"],[])

    def test_collects_registered_child_confirmations_without_changing_ids(self):
        item=child("c1","care");item["status"]="WAITING_CONFIRMATION";item["confirmationIds"]=["confirm-1","confirm-2"]
        value=collect_child_confirmations("root",[item])
        self.assertEqual(value,{"confirmationIds":["confirm-1","confirm-2"],"domains":["care"]})


if __name__=="__main__":unittest.main()
