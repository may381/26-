"""支付前确认的规则测试：该拦的拦、不该拦的绝不打扰。"""
import unittest

from payment_guard import check


class PaymentGuardTests(unittest.TestCase):
    def test_classic_advance_fee_triggers_high(self):
        result = check("您报名的课程可全额退款，请先缴纳2000元保证金，再把验证码发给客服。")
        self.assertIsNotNone(result)
        self.assertEqual(result["triggered"], True)
        self.assertEqual(result["risk"], "high")
        self.assertIn("先付款", result["groups"])
        self.assertIn("索要敏感信息", result["groups"])
        self.assertTrue(any("保证金" == m or "验证码" == m for m in result["matched"]))

    def test_police_impersonation_with_transfer_triggers(self):
        result = check("我是公安局的，你的账户涉嫌洗钱，请转到安全账户否则马上拘留。")
        self.assertIsNotNone(result)
        self.assertIn("冒充身份", result["groups"])
        self.assertIn("施压话术", result["groups"])

    def test_single_group_is_medium(self):
        result = check("客服让我先交300元手续费才能退钱。")
        self.assertIsNotNone(result)
        self.assertEqual(result["risk"], "high")  # 含"先付款"即高危
        only_pressure = check("对方说逾期就起诉我。")
        self.assertIsNotNone(only_pressure)
        self.assertEqual(only_pressure["risk"], "medium")

    def test_negation_is_not_a_hit(self):
        self.assertIsNone(check("社区读书会免费参加，不需要转账，也不收任何费用。"))
        self.assertIsNone(check("这个通知说不用付钱，也没有验证码。"))

    def test_normal_notice_never_triggers(self):
        self.assertIsNone(check("本周六上午九点文化站二楼有读书会，欢迎参加。"))
        self.assertIsNone(check("今天天气不错，适合出门走走。"))

    def test_always_declares_no_action_taken(self):
        result = check("请先交保证金再把验证码发我。")
        self.assertIn("未执行任何转账、支付或汇款", result["notExecuted"])
        self.assertIn("不承诺能追回", " ".join(result["notExecuted"]))

    def test_never_outputs_probability_or_verdict(self):
        result = check("我是客服，请提供银行卡号和密码。")
        blob = str(result)
        self.assertNotIn("概率", blob)
        self.assertNotIn("已报警", blob)
        self.assertNotIn("已拦截", blob)
        self.assertIn("不是警方的认定", blob)

    def test_empty_or_oversized_input_is_ignored(self):
        self.assertIsNone(check(""))
        self.assertIsNone(check("   "))
        self.assertIsNone(check(None))
        self.assertIsNone(check("转账" * 3000))

    def test_structure_is_stable_for_ui(self):
        result = check("先交保证金，再发验证码。")
        for key in ("triggered", "risk", "groups", "matched", "headline",
                    "riskPoints", "pauseSteps", "channels", "notExecuted", "note"):
            self.assertIn(key, result)
        self.assertTrue(all({"name", "note"} <= set(c) for c in result["channels"]))
        self.assertGreaterEqual(len(result["pauseSteps"]), 3)


if __name__ == "__main__":
    unittest.main()
