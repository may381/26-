import unittest
from p2_client import P2Error
from recovery import integrate_confirmation_decisions, integrate_recovery


def action(status="SUCCEEDED"):
    return {"stepId":"s1","actionId":"a1","tool":"memory.change","argsDigest":"sha256-x",
            "confirmationId":"c1","executionStatus":status,"effectId":"e1" if status=="SUCCEEDED" else None,
            "businessRef":None,"externalStatus":None,"lastError":None,"retryPolicy":"NO_RETRY"}


def confirmation(state="EXECUTED",action_status="SUCCEEDED"):
    return {"confirmationId":"c1","ownerTaskId":"root","rootTaskId":"root","actionId":"a1",
            "version":2,"state":state,"operation":"memory.change","summary":"保存步行偏好",
            "expiresAt":"2026-11-07T01:00:00Z","actionStatus":action_status,
            "lastError":None,"canRetry":False}


class RecoveryTests(unittest.TestCase):
    def test_confirmed_success_requires_matching_ledger(self):
        value=integrate_confirmation_decisions("root",[confirmation()],[action()])
        self.assertEqual(value["outcome"],"SUCCEEDED");self.assertIn("已执行",value["reply"])

    def test_rejected_confirmation_does_not_require_execution(self):
        value=integrate_confirmation_decisions("root",[confirmation("REJECTED","NOT_STARTED")],[action("NOT_STARTED")])
        self.assertEqual(value["outcome"],"FAILED");self.assertIn("已拒绝",value["reply"])

    def test_unknown_confirmation_never_replays(self):
        with self.assertRaises(P2Error):
            integrate_confirmation_decisions("root",[confirmation("EXECUTION_UNKNOWN","UNKNOWN")],[action("UNKNOWN")])

    def test_recovery_summarizes_terminal_ledger(self):
        value=integrate_recovery("root",[action("SUCCEEDED")])
        self.assertEqual(value["outcome"],"SUCCEEDED");self.assertIn("memory.change",value["reply"])

    def test_recovery_stops_on_running_unknown_or_not_started(self):
        for status in ("RUNNING","UNKNOWN","PREPARED","NOT_STARTED"):
            with self.assertRaises(P2Error):integrate_recovery("root",[action(status)])


if __name__=="__main__":unittest.main()
