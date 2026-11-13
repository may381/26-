"""A3 v3 服务自测（起真服务、打真 HTTP 请求）。"""

from __future__ import annotations

import json
import os
import sys
import threading
import unittest
import uuid
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import schema_check  # noqa: E402
import v3_messages  # noqa: E402
from v3_server import (  # noqa: E402
    Receipt, V3Service, _call, _sample_body, create_server, detect_domain,
)


def start(service: V3Service):
    server = create_server(0, service)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


class DetectDomainTest(unittest.TestCase):
    """判错领域比不判更糟 —— 老人会被莫名转走。"""

    def test_culture_texts(self):
        for text in ("想学剪纸", "有没有书法班", "想参加文化活动", "太极课在哪",
                     "想学个非遗手艺"):
            with self.subTest(text=text):
                self.assertEqual(detect_domain(text), "culture")

    def test_health_texts(self):
        for text in ("帮我看看血压高不高", "我头晕", "这个药怎么吃"):
            with self.subTest(text=text):
                self.assertEqual(detect_domain(text), "health")

    def test_fraud_and_help(self):
        self.assertEqual(detect_domain("好像被骗了"), "fraud")
        self.assertEqual(detect_domain("我摔倒了"), "help")

    def test_culture_word_wins_over_other_signals(self):
        """「文化活动室离医院远不远」里有"医院"，但主语是文化，不能判成健康。"""
        self.assertEqual(detect_domain("文化活动室离医院远不远"), "culture")

    def test_unknown_defaults_to_culture(self):
        for text in ("", "   ", "你好", "在吗"):
            with self.subTest(text=text):
                self.assertEqual(detect_domain(text), "culture")


class ServiceTest(unittest.TestCase):
    """服务层逻辑，不走 HTTP。"""

    def setUp(self):
        self.service = V3Service()

    def test_successful_invocation_returns_valid_response(self):
        status, body = self.service.handle_invocation(_sample_body("想学剪纸"))
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["control"]["next"], "COMPLETE")
        folder = v3_messages.schema_dir()
        root = schema_check.load_schema(os.path.join(folder, "control.schema.json"))
        schema_check.validate(body, root["definitions"]["AgentResponse"], root)

    def test_idempotent_same_invocation_id(self):
        body = _sample_body("想学剪纸", "invoke-fixed-001")
        first = self.service.handle_invocation(body)
        second = self.service.handle_invocation(dict(body))
        self.assertEqual(first, second, "同一个 invocationId 必须返回同样的结果")
        self.assertEqual(len(self.service._receipts), 1)

    def test_receipt_records_finish(self):
        body = _sample_body("想学剪纸", "invoke-fixed-002")
        self.service.handle_invocation(body)
        status, payload = self.service.get_receipt("invoke-fixed-002")
        self.assertEqual(status, 200)
        self.assertEqual(payload["data"]["status"], "FINISHED")
        self.assertIsNotNone(payload["data"]["result"])

    def test_receipt_missing_is_404(self):
        status, payload = self.service.get_receipt("nope")
        self.assertEqual(status, 404)
        self.assertEqual(payload["code"], "NOT_FOUND")

    def test_vague_request_asks_once(self):
        status, body = self.service.handle_invocation(_sample_body("我想参加文化活动"))
        self.assertEqual(status, 200)
        control = body["data"]["control"]
        self.assertEqual(control["next"], "WAIT_INPUT")
        self.assertIsNone(control["outcome"])
        self.assertLessEqual(len(control["inputRequest"]["options"]), 4)

    def test_expired_deadline_is_504(self):
        status, body = self.service.handle_invocation(
            _sample_body("想学剪纸", deadline_offset_s=-60))
        self.assertEqual(status, 504)
        self.assertEqual(body["code"], "UPSTREAM_TIMEOUT")

    def test_other_domain_is_503(self):
        status, body = self.service.handle_invocation(_sample_body("帮我看看血压"))
        self.assertEqual(status, 503)
        self.assertEqual(body["code"], "CAPABILITY_UNAVAILABLE")

    def test_bad_version_is_400(self):
        body = _sample_body()
        body["protocolVersion"] = "2.0"
        status, payload = self.service.handle_invocation(body)
        self.assertEqual(status, 400)
        self.assertEqual(payload["code"], "UNSUPPORTED_PROTOCOL_VERSION")

    def test_failed_invocation_is_recorded(self):
        body = _sample_body("想学剪纸", "invoke-fixed-003", deadline_offset_s=-60)
        self.service.handle_invocation(body)
        _, payload = self.service.get_receipt("invoke-fixed-003")
        self.assertEqual(payload["data"]["status"], "FAILED")
        self.assertEqual(payload["data"]["error"]["code"], "UPSTREAM_TIMEOUT")

    def test_cancel_running_marks_cancelled(self):
        self.service._receipts["invoke-x"] = Receipt(invocation_id="invoke-x",
                                                     task_id="child-1", status="RUNNING")
        status, body = self.service.cancel("invoke-x", {
            "protocolVersion": "3.0", "invocationId": "invoke-x",
            "cancelRequestId": "cancel-1", "reason": "改主意"})
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["status"], "CANCELLED")

    def test_cancel_then_resend_is_not_runnable(self):
        self.service._receipts["invoke-y"] = Receipt(invocation_id="invoke-y",
                                                     task_id="child-1", status="RUNNING")
        self.service.cancel("invoke-y", {"protocolVersion": "3.0", "invocationId": "invoke-y",
                                         "cancelRequestId": "cancel-1", "reason": "x"})
        status, body = self.service.handle_invocation(
            _sample_body("想学剪纸", "invoke-y"))
        self.assertEqual(status, 409)
        self.assertEqual(body["code"], "TASK_NOT_RUNNABLE")

    def test_cancel_finished_is_rejected(self):
        body = _sample_body("想学剪纸", "invoke-z")
        self.service.handle_invocation(body)
        status, payload = self.service.cancel("invoke-z", {
            "protocolVersion": "3.0", "invocationId": "invoke-z",
            "cancelRequestId": "cancel-1", "reason": "晚了"})
        self.assertEqual(status, 409)
        self.assertEqual(payload["code"], "TASK_NOT_RUNNABLE")

    def test_cancel_missing_invocation_is_404(self):
        status, payload = self.service.cancel("ghost", {
            "protocolVersion": "3.0", "invocationId": "ghost",
            "cancelRequestId": "cancel-1", "reason": "x"})
        self.assertEqual(status, 404)

    def test_cancel_path_body_mismatch_is_400(self):
        status, payload = self.service.cancel("invoke-a", {
            "protocolVersion": "3.0", "invocationId": "invoke-b",
            "cancelRequestId": "cancel-1", "reason": "x"})
        self.assertEqual(status, 400)
        self.assertEqual(payload["code"], "INVALID_ARGUMENT")

    def test_cancel_requires_cancel_request_id(self):
        self.service._receipts["invoke-c"] = Receipt(invocation_id="invoke-c",
                                                     task_id="t", status="RUNNING")
        status, _ = self.service.cancel("invoke-c", {"protocolVersion": "3.0",
                                                     "invocationId": "invoke-c",
                                                     "reason": "x"})
        self.assertEqual(status, 400)

    def test_health_reports_no_personal_data(self):
        status, body = self.service.health()
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["status"], "UP")
        dumped = json.dumps(body, ensure_ascii=False)
        for leaked in ("userId", "u100", "剪纸"):
            self.assertNotIn(leaked, dumped)


class CultureBranchTest(unittest.TestCase):
    """文化课的三种走法：给结果 / 反问 / 直说没有。三者不能混。"""

    def setUp(self):
        self.service = V3Service()

    def ask(self, text):
        status, body = self.service.handle_invocation(
            _sample_body(text, f"invoke-{uuid.uuid4().hex[:8]}"))
        return status, body["data"]

    def test_known_interest_gives_cards(self):
        status, data = self.ask("想学剪纸")
        self.assertEqual(status, 200)
        self.assertEqual(data["control"]["next"], "COMPLETE")
        self.assertGreater(data["results"][0]["payload"]["totalCandidates"], 0)

    def test_generic_request_asks_back(self):
        for text in ("我想参加文化活动", "有什么班", "想学点手艺"):
            with self.subTest(text=text):
                _, data = self.ask(text)
                self.assertEqual(data["control"]["next"], "WAIT_INPUT")
                self.assertIsNotNone(data["control"]["inputRequest"])

    def test_specific_but_unsupported_says_no_instead_of_asking(self):
        """老人想学跳伞，我们有剪纸班但不是他想要的 —— 直说没有，再给现有的。

        这里最容易写错成"反问学哪一类"，读起来像没听懂人话。
        """
        status, data = self.ask("想学跳伞")
        self.assertEqual(status, 200)
        self.assertEqual(data["control"]["next"], "COMPLETE")
        self.assertIsNone(data["control"]["inputRequest"])
        self.assertIn("没有开班", data["reply"]["text"])
        self.assertEqual(data["results"][0]["payload"]["totalCandidates"], 0)

    def test_full_class_returns_empty_not_question(self):
        """二胡班名额已满，是"有这门课但去不了"，不是"没听懂"。"""
        _, data = self.ask("想学民乐")
        self.assertEqual(data["control"]["next"], "COMPLETE")
        self.assertEqual(data["results"][0]["payload"]["totalCandidates"], 0)

    def test_xue_char_alone_does_not_trigger_asking(self):
        """"学"这个字不能当"问的是大类"的信号，否则"想学跳伞"会被反问。"""
        _, data = self.ask("想学跳伞")
        self.assertIsNone(data["control"]["inputRequest"])


class ExtendedDispatchTest(unittest.TestCase):
    """六条分流的分界。判错的后果是"想找课的人被念了一段非遗介绍"。"""

    def setUp(self):
        self.service = V3Service()

    def ask(self, text):
        status, body = self.service.handle_invocation(
            _sample_body(text, f"invoke-{uuid.uuid4().hex[:8]}"))
        return status, body

    def card_type(self, text):
        _, body = self.ask(text)
        results = body["data"].get("results") or [{}]
        return results[0].get("type")

    # ---- 知识问答 vs 课程推荐
    def test_knowledge_question_goes_to_knowledge(self):
        self.assertEqual(self.card_type("剪纸是什么"), "culture.knowledge_answer")

    def test_dialect_question_goes_to_knowledge(self):
        self.assertEqual(self.card_type("唔该是什么意思"), "culture.knowledge_answer")

    def test_learning_intent_goes_to_courses_not_knowledge(self):
        """「想学剪纸」是要找课，不能回一段非遗介绍。"""
        self.assertEqual(self.card_type("想学剪纸"), "culture.course_candidates")

    def test_course_query_with_class_word_goes_to_courses(self):
        self.assertEqual(self.card_type("有没有剪纸班"), "culture.course_candidates")

    def test_unknown_knowledge_admits_it(self):
        _, body = self.ask("景泰蓝怎么烧制")
        self.assertEqual(body["data"]["results"][0]["type"], "culture.knowledge_answer")
        self.assertEqual(body["data"]["results"][0]["payload"]["totalCandidates"], 0)
        self.assertIn("没有现成资料", body["data"]["reply"]["text"])

    # ---- 能力银行 vs 课程
    def test_skill_claim_goes_to_ability(self):
        self.assertEqual(self.card_type("我会剪纸，愿意教大家"), "ability.skill_registration")

    def test_want_to_learn_does_not_register_skill(self):
        """「想学剪纸」绝不能生成技能登记 —— 那是老人没说过的供给。"""
        self.assertNotEqual(self.card_type("想学剪纸"), "ability.skill_registration")

    def test_skill_registration_is_not_published(self):
        _, body = self.ask("我会剪纸，愿意教大家")
        payload = body["data"]["results"][0]["payload"]
        self.assertEqual(payload["skill"]["state"], "SUBMITTED")
        self.assertFalse(payload["nextAction"]["a3CanAdvance"])

    # ---- 数据驱动分支
    def _with_card(self, text, result_type, payload):
        body = _sample_body(text, f"invoke-{uuid.uuid4().hex[:8]}")
        body["context"]["reason"] = "CHILDREN_FINISHED"
        body["context"]["dependencyResults"] = [{
            "taskId": "child-020", "parentTaskId": "root-001",
            "targetAgent": "a2", "domain": "culture", "required": True,
            "version": 1, "status": "SUCCEEDED",
            "reply": {"text": "数据已备好", "speechRate": 0.9, "audioUrl": None},
            "results": [{"resultId": "d-1", "type": result_type,
                         "schemaVersion": "1.0", "title": "数据", "businessRef": None,
                         "availability": "DEMO", "generatedAt": "2026-11-09T00:00:00Z",
                         "sources": [], "pendingChecks": [], "payload": payload}],
            "inputRequest": None, "confirmationIds": [], "effectIds": [],
            "error": None, "completedAt": "2026-11-09T00:00:00Z",
        }]
        return self.service.handle_invocation(body)

    def test_learning_progress_from_attendance_card(self):
        status, body = self._with_card("我学得怎么样", "culture.attendance_records", {
            "course": {"courseId": "demo-papercut-01", "title": "剪纸入门班",
                       "durationMin": 90},
            "sessions": [{"durationMin": 90, "status": "ATTENDED"}] * 2
                        + [{"durationMin": 0, "status": "ABSENT"}],
        })
        self.assertEqual(status, 200)
        card = body["data"]["results"][0]
        self.assertEqual(card["type"], "culture.learning_progress")
        self.assertEqual(card["payload"]["attendedCount"], 2)
        self.assertEqual(card["payload"]["actualMinutes"], 180)

    def test_contribution_summary_from_card(self):
        status, body = self._with_card("我一共帮了多久", "ability.contribution_records", {
            "records": [
                {"recordId": "c1", "skillName": "剪纸", "minutes": 90, "status": "CONFIRMED"},
                {"recordId": "c2", "skillName": "剪纸", "minutes": 90, "status": "CONFIRMED"},
                {"recordId": "c3", "skillName": "书法", "minutes": 60, "status": "PENDING"},
            ]})
        self.assertEqual(status, 200)
        card = body["data"]["results"][0]
        self.assertEqual(card["type"], "ability.contribution_summary")
        self.assertEqual(card["payload"]["summary"]["totalTimes"], 2)
        self.assertEqual(card["payload"]["summary"]["pendingCount"], 1)
        self.assertFalse(card["payload"]["a3ModifiedAnything"])

    def test_all_new_cards_pass_schema(self):
        folder = v3_messages.schema_dir()
        root = schema_check.load_schema(os.path.join(folder, "control.schema.json"))
        for text in ("剪纸是什么", "唔该是什么意思", "我会剪纸，愿意教大家",
                     "想学剪纸", "景泰蓝怎么烧制"):
            with self.subTest(text=text):
                _, body = self.ask(text)
                schema_check.validate(body, root["definitions"]["AgentResponse"], root)
                for card in body["data"]["results"]:
                    schema_check.validate(card, root["definitions"]["Result"], root)


class MemoryReviewTest(unittest.TestCase):
    """记忆候选审核接进服务后的行为。

    审核是 A3 在 v3 里唯一独占的职责，协议 line 754 要求：
    返回 MEMORY_REVIEW 类型结果，payload 就是那 9 个字段，不能带伪造的确认号。
    """

    CANDIDATE = {
        "candidateId": "cand-001", "candidateVersion": 1,
        "category": "LONG_TERM_PREFERENCE", "key": "culture.interests",
        "content": "喜欢剪纸和刺绣", "domains": ["culture"], "sensitivity": "GENERAL",
    }

    @staticmethod
    def invocation_with(candidate: dict, invocation_id: str = "invoke-review-1") -> dict:
        body = _sample_body("审核这条候选", invocation_id)
        body["context"]["reason"] = "CHILDREN_FINISHED"
        body["context"]["dependencyResults"] = [{
            "taskId": "child-010", "parentTaskId": "root-001",
            "targetAgent": "a2", "domain": "culture", "required": True,
            "version": 1, "status": "SUCCEEDED",
            "reply": {"text": "候选已生成", "speechRate": 0.9, "audioUrl": None},
            "results": [{
                "resultId": "cand-result-1", "type": "MEMORY_CANDIDATE",
                "schemaVersion": "1.0", "title": "候选", "businessRef": None,
                "availability": "DEMO", "generatedAt": "2026-11-03T00:00:00Z",
                "sources": [], "pendingChecks": [], "payload": candidate,
            }],
            "inputRequest": None, "confirmationIds": [], "effectIds": [],
            "error": None, "completedAt": "2026-11-03T00:00:00Z",
        }]
        return body

    _UNSET = object()

    def run_review(self, candidate=None, memories=_UNSET, invocation_id="invoke-review-1"):
        # memories 的默认值必须是"确实查过、没有记忆"（[]），不能是 None。
        # None 在新契约里表示"读不到库"，那是 503 的分支，测试要显式传。
        recalled = [] if memories is self._UNSET else memories
        service = V3Service(memories_factory=lambda user_id: recalled)
        return service.handle_invocation(
            self.invocation_with(candidate or dict(self.CANDIDATE), invocation_id))

    # ---- 五种建议各走一遍
    def test_no_existing_memory_suggests_add(self):
        status, body = self.run_review()
        self.assertEqual(status, 200)
        payload = body["data"]["results"][0]["payload"]
        self.assertEqual(payload["recommendation"], "ADD")
        self.assertEqual(body["data"]["control"]["next"], "COMPLETE")
        self.assertEqual(body["data"]["usedMemoryRefs"], [])

    def test_identical_memory_suggests_keep(self):
        existing = [{"memoryId": "m-1", "version": 2, "key": "culture.interests",
                     "state": "ACTIVE", "content": "喜欢剪纸和刺绣",
                     "value": None, "domains": ["culture"]}]
        status, body = self.run_review(memories=existing)
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["results"][0]["payload"]["recommendation"], "KEEP")
        # 读过哪条记忆必须如实登记，否则 P2 没法追溯建议依据
        self.assertEqual(body["data"]["usedMemoryRefs"], [{"memoryId": "m-1", "version": 2}])

    def test_changed_content_suggests_replace(self):
        existing = [{"memoryId": "m-1", "version": 2, "key": "culture.interests",
                     "state": "ACTIVE", "content": "只喜欢剪纸",
                     "value": None, "domains": ["culture"]}]
        status, body = self.run_review(memories=existing)
        self.assertEqual(body["data"]["results"][0]["payload"]["recommendation"], "REPLACE")
        self.assertTrue(body["data"]["results"][0]["payload"]["needsUserConfirmation"])

    def test_wider_domains_suggests_merge(self):
        existing = [{"memoryId": "m-9", "version": 1, "key": "culture.interests",
                     "state": "ACTIVE", "content": "喜欢剪纸和刺绣",
                     "value": None, "domains": ["culture", "health"]}]
        _, body = self.run_review(memories=existing)
        payload = body["data"]["results"][0]["payload"]
        self.assertEqual(payload["recommendation"], "MERGE")
        self.assertTrue(payload["needsUserConfirmation"], "扩大领域必须重新确认")

    def test_sensitive_without_consent_is_rejected(self):
        sensitive = dict(self.CANDIDATE, sensitivity="SENSITIVE")
        _, body = self.run_review(candidate=sensitive)
        payload = body["data"]["results"][0]["payload"]
        self.assertEqual(payload["recommendation"], "REJECT")
        self.assertFalse(payload["needsUserConfirmation"])

    # ---- 三态：读不到记忆 ≠ 没有记忆
    def test_unreadable_memory_is_503_not_add(self):
        """最要紧的一条：读不到库就说读不到，绝不能报 ADD 蒙一个建议。"""
        status, body = self.run_review(memories=None)
        self.assertEqual(status, 503)
        self.assertEqual(body["code"], "CAPABILITY_UNAVAILABLE")
        self.assertIsNone(body["data"])

    def test_empty_memory_list_is_not_503(self):
        """空列表是"确实没有"，不是"查不了"，要正常给 ADD。"""
        status, body = self.run_review(memories=[])
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["results"][0]["payload"]["recommendation"], "ADD")

    # ---- 结果卡片
    def test_result_card_shape(self):
        _, body = self.run_review()
        card = body["data"]["results"][0]
        folder = v3_messages.schema_dir()
        root = schema_check.load_schema(os.path.join(folder, "control.schema.json"))
        schema_check.validate(card, root["definitions"]["Result"], root)
        self.assertEqual(card["type"], "MEMORY_REVIEW")
        self.assertIsNone(card["businessRef"])
        self.assertEqual(card["availability"], "NEEDS_VERIFICATION")
        self.assertEqual(card["sources"][0]["id"], "cand-001")

    def test_payload_has_exactly_nine_fields(self):
        _, body = self.run_review()
        payload = body["data"]["results"][0]["payload"]
        self.assertEqual(set(payload), {
            "candidateId", "candidateVersion", "reviewId", "reviewVersion",
            "recommendation", "conflictMemoryRefs", "proposedDomains",
            "needsUserConfirmation", "explanation",
        })

    def test_payload_matches_official_schema(self):
        _, body = self.run_review()
        folder = v3_messages.schema_dir()
        root = schema_check.load_schema(os.path.join(folder, "control.schema.json"))
        schema_check.validate(body["data"]["results"][0]["payload"],
                              root["definitions"]["MemoryReview"], root)

    def test_no_fake_confirmation_id(self):
        """协议明说：不能包含伪造的 confirmationId。"""
        _, body = self.run_review()
        self.assertEqual(body["data"]["confirmationIds"], [])
        self.assertNotIn("confirmationId", body["data"]["results"][0]["payload"])

    def test_intent_follows_candidate_domain(self):
        """审核跨领域：健康候选要算 health，不能被文化限制挡住。"""
        health = dict(self.CANDIDATE, key="health.bloodPressure",
                      content="有高血压", domains=["health"])
        status, body = self.run_review(candidate=health)
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["intent"], "health")
        self.assertIn("health", body["data"]["domains"])

    def test_reply_is_human_readable(self):
        _, body = self.run_review()
        text = body["data"]["reply"]["text"]
        self.assertTrue(text)
        for jargon in ("ADD", "REPLACE", "MERGE", "candidateId", "recommendation"):
            self.assertNotIn(jargon, text)

    # ---- 非法输入
    def test_candidate_without_content_is_400(self):
        status, body = self.run_review(candidate={"candidateId": "cand-9"})
        self.assertEqual(status, 400)
        self.assertIn("content", body["message"])

    def test_candidate_without_id_is_400(self):
        status, body = self.run_review(candidate={"content": "喜欢剪纸"})
        self.assertEqual(status, 400)
        self.assertIn("candidateId", body["message"])

    def test_business_ref_only_is_400(self):
        """只给了 id/version 的引用、没有内容，要说不清楚，不能瞎审。"""
        body = _sample_body("审核", "invoke-ref-only")
        body["context"]["businessRefs"] = [{"type": "MEMORY_CANDIDATE",
                                            "id": "cand-001", "version": 1}]
        status, response = V3Service().handle_invocation(body)
        self.assertEqual(status, 400)
        self.assertIn("dependencyResults", response["message"])

    def test_review_is_idempotent(self):
        service = V3Service()
        body = self.invocation_with(dict(self.CANDIDATE), "invoke-review-fixed")
        first = service.handle_invocation(dict(body))
        second = service.handle_invocation(body)
        self.assertEqual(first, second)
        self.assertEqual(len(service._receipts), 1)



    """走真 HTTP，验证路由和状态码。"""

    @classmethod
    def setUpClass(cls):
        cls.service = V3Service()
        cls.server, cls.port = start(cls.service)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def post(self, path, body):
        return _call(self.port, "POST", path, body)

    def get(self, path):
        return _call(self.port, "GET", path)

    def test_health(self):
        status, body = self.get("/health")
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["protocolVersion"], "3.0")

    def test_messages_round_trip(self):
        status, body = self.post("/internal/v3/messages", _sample_body("想学刺绣"))
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["domains"], ["culture", "tourism"])

    def test_receipt_route(self):
        invocation_id = f"invoke-{uuid.uuid4().hex[:8]}"
        self.post("/internal/v3/messages", _sample_body("想学剪纸", invocation_id))
        status, body = self.get(f"/internal/v3/invocations/{invocation_id}")
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["status"], "FINISHED")

    def test_cancel_route(self):
        invocation_id = f"invoke-{uuid.uuid4().hex[:8]}"
        self.service._receipts[invocation_id] = Receipt(
            invocation_id=invocation_id, task_id="t", status="RUNNING")
        status, body = self.post(f"/internal/v3/invocations/{invocation_id}/cancel", {
            "protocolVersion": "3.0", "invocationId": invocation_id,
            "cancelRequestId": "cancel-http-1", "reason": "改主意"})
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["status"], "CANCELLED")

    def test_unknown_route_is_404(self):
        self.assertEqual(self.get("/nope")[0], 404)
        self.assertEqual(self.post("/nope", {})[0], 404)

    def test_empty_body_is_400(self):
        status, body = _call(self.port, "POST", "/internal/v3/messages", None)
        self.assertEqual(status, 400)
        self.assertEqual(body["code"], "INVALID_ARGUMENT")

    def test_non_json_body_is_400(self):
        import urllib.error
        import urllib.request

        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/internal/v3/messages",
            data=b"not json at all", method="POST",
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
                code = response.status
        except urllib.error.HTTPError as error:
            payload = json.loads(error.read().decode("utf-8"))
            code = error.code
        self.assertEqual(code, 400)
        self.assertEqual(payload["code"], "INVALID_ARGUMENT")

    def test_protocol_header_is_returned(self):
        import urllib.request

        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/health", method="GET")
        with urllib.request.urlopen(request, timeout=10) as response:
            self.assertEqual(response.headers.get("X-Agent-Protocol-Version"), "3.0")
            self.assertTrue(response.headers.get("X-Trace-Id"))


class AuthTest(unittest.TestCase):
    """配了密钥就必须校验 —— 演示时能不带，上线时不能裸奔。"""

    @classmethod
    def setUpClass(cls):
        cls.service = V3Service(agent_key="secret-123")
        cls.server, cls.port = start(cls.service)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_missing_key_is_401(self):
        status, body = _call(self.port, "POST", "/internal/v3/messages", _sample_body())
        self.assertEqual(status, 401)
        self.assertEqual(body["code"], "UNAUTHORIZED")

    def test_wrong_key_is_401(self):
        import urllib.error
        import urllib.request

        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/internal/v3/messages",
            data=json.dumps(_sample_body()).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json", "X-Agent-Key": "wrong"})
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                code = response.status
        except urllib.error.HTTPError as error:
            code = error.code
        self.assertEqual(code, 401)

    def test_correct_key_passes(self):
        import urllib.request

        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/internal/v3/messages",
            data=json.dumps(_sample_body("想学剪纸")).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json", "X-Agent-Key": "secret-123"})
        with urllib.request.urlopen(request, timeout=10) as response:
            self.assertEqual(response.status, 200)

    def test_health_needs_no_key(self):
        self.assertEqual(_call(self.port, "GET", "/health")[0], 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
