"""v3 报文信封自测（收 InvocationRequest / 回 AgentResponse / 16 个错误码）。"""

from __future__ import annotations

import copy
import json
import os
import sys
import unittest
import uuid
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import schema_check  # noqa: E402
import v3_messages  # noqa: E402
from v3_messages import (  # noqa: E402
    DOMAINS, ERROR_STATUS, NEXT_COMPLETE, NEXT_WAIT_CONFIRMATION,
    NEXT_WAIT_DEPENDENCIES, NEXT_WAIT_INPUT, OUTCOME_FAILED, OUTCOME_SUCCEEDED,
    Invocation, ProtocolError, build_handoff, build_response, error_response,
    from_exception, new_input_request, parse_invocation, relay_question,
    settle_control, verify_used_memory_refs,
)

def _schema_dir() -> str:
    """优先用仓库自带的 schemas/，最后才回退到工作区外的官方开发包。

    以前这里写死了 `../_v3开发包/agent-v3-r3`，结果队友 clone 下来
    一个测试都跑不了 —— 那个目录只在某台机器上存在。
    """
    for candidate in (os.environ.get("A3_SCHEMA_DIR") or "",
                      os.path.join(ROOT, "schemas"),
                      os.path.join(ROOT, "..", "_v3开发包", "agent-v3-r3")):
        if candidate and os.path.exists(os.path.join(candidate, "control.schema.json")):
            return candidate
    raise RuntimeError("找不到 control.schema.json：仓库里的 schemas/ 目录应自带它")


TOKEN = "DEMO-TOKEN-NOT-A-REAL-CREDENTIAL"


def load_schema() -> dict:
    return schema_check.load_schema(os.path.join(_schema_dir(), "control.schema.json"))


def load_examples() -> dict:
    return schema_check.load_schema(os.path.join(_schema_dir(), "examples.json"))


def make_body(**overrides) -> dict:
    """一份最小合法 InvocationRequest，按需覆盖字段。"""
    body = {
        "protocolVersion": "3.0",
        "userId": "u100",
        "conversationId": "conv-001",
        "messageId": "msg-001",
        "task": {"id": "child-002", "parentTaskId": "root-001", "version": 3,
                 "attempt": 1, "invocationId": "invoke-child-002",
                 "deadlineAt": "2030-10-29T02:01:00Z"},
        "input": {"text": "想学剪纸，别太远", "attachmentIds": []},
        "context": {"businessRefs": [], "history": [], "completedEffects": [],
                    "reason": "USER_MESSAGE", "candidateTasks": [],
                    "dependencyResults": [], "confirmationResults": [],
                    "actionLedger": [], "planSteps": [],
                    "readSet": {"memoryRevision": 12, "authorizationRevision": 4,
                                "provenanceRefs": []},
                    "inputResponse": None, "pendingInputRequests": []},
        "capabilityToken": TOKEN,
    }
    body.update(overrides)
    return body


class InvocationParsingTest(unittest.TestCase):
    """收得进来。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.root = load_schema()

    def parse(self, body):
        return parse_invocation(body, root_schema=self.root)

    # ---- 正常
    def test_parses_minimal_body(self):
        inv = self.parse(make_body())
        self.assertEqual(inv.task_id, "child-002")
        self.assertEqual(inv.parent_task_id, "root-001")
        self.assertEqual(inv.task_version, 3)
        self.assertEqual(inv.text, "想学剪纸，别太远")
        self.assertEqual(inv.memory_revision, 12)
        self.assertFalse(inv.is_root)

    def test_root_task_has_no_parent(self):
        body = make_body()
        body["task"]["parentTaskId"] = None
        self.assertTrue(self.parse(body).is_root)

    def test_attachment_only_input_is_allowed(self):
        """只有图片没有文字也要能过 —— 老人可能只发一张照片。"""
        body = make_body()
        body["input"] = {"text": "  ", "attachmentIds": ["att-1"]}
        self.assertEqual(self.parse(body).attachment_ids, ("att-1",))

    def test_deadline_in_past_is_detected_not_rejected(self):
        """过期是 P2 的判断，A3 只负责能看出来，不擅自拒绝。"""
        body = make_body()
        body["task"]["deadlineAt"] = (
            datetime.now(timezone.utc) - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertTrue(self.parse(body).deadline_passed())

    # ---- 版本
    def test_wrong_version_is_rejected_first(self):
        for bad in ("2.0", "3", None, ""):
            with self.subTest(version=bad):
                with self.assertRaises(ProtocolError) as caught:
                    self.parse(make_body(protocolVersion=bad))
                self.assertEqual(caught.exception.code, "UNSUPPORTED_PROTOCOL_VERSION")
                self.assertEqual(caught.exception.status, 400)

    def test_version_checked_before_shape(self):
        """版本错 + 缺字段时，必须报版本错，不能误导成「缺 task」。"""
        with self.assertRaises(ProtocolError) as caught:
            self.parse({"protocolVersion": "1.0"})
        self.assertEqual(caught.exception.code, "UNSUPPORTED_PROTOCOL_VERSION")

    # ---- 密钥
    def test_missing_token_is_401(self):
        for bad in (None, "", "   ", 123):
            with self.subTest(token=bad):
                body = make_body()
                if bad is None:
                    body.pop("capabilityToken")
                else:
                    body["capabilityToken"] = bad
                with self.assertRaises(ProtocolError) as caught:
                    self.parse(body)
                self.assertEqual(caught.exception.status, 401)
                self.assertEqual(caught.exception.code, "UNAUTHORIZED")

    def test_expected_token_must_match(self):
        with self.assertRaises(ProtocolError) as caught:
            parse_invocation(make_body(), expected_token="other", root_schema=self.root)
        self.assertEqual(caught.exception.code, "UNAUTHORIZED")

    def test_legacy_v2_token_name_is_named_explicitly(self):
        """用 v2 的 toolContextToken 时要说清楚，别只报「缺字段」。"""
        body = make_body()
        body.pop("capabilityToken")
        body["toolContextToken"] = TOKEN
        with self.assertRaises(ProtocolError) as caught:
            self.parse(body)
        self.assertIn("toolContextToken", caught.exception.message)

    # ---- 形状
    def test_missing_required_field_is_invalid_argument(self):
        for field in ("userId", "conversationId", "messageId", "task", "input", "context"):
            with self.subTest(field=field):
                body = make_body()
                body.pop(field)
                with self.assertRaises(ProtocolError) as caught:
                    self.parse(body)
                self.assertEqual(caught.exception.code, "INVALID_ARGUMENT")

    def test_each_context_field_is_required(self):
        for field in ("businessRefs", "history", "completedEffects", "reason",
                      "candidateTasks", "dependencyResults", "confirmationResults",
                      "actionLedger", "planSteps", "readSet", "inputResponse",
                      "pendingInputRequests"):
            with self.subTest(field=field):
                body = make_body()
                body["context"].pop(field)
                with self.assertRaises(ProtocolError):
                    self.parse(body)

    def test_unknown_top_level_field_is_rejected(self):
        with self.assertRaises(ProtocolError) as caught:
            self.parse(make_body(extraField="多余"))
        self.assertEqual(caught.exception.code, "INVALID_ARGUMENT")

    def test_non_object_body_is_rejected(self):
        for bad in ([], "", 3, None):
            with self.subTest(body=bad):
                with self.assertRaises(ProtocolError) as caught:
                    parse_invocation(bad, root_schema=self.root)
                self.assertEqual(caught.exception.code, "INVALID_ARGUMENT")

    # ---- 语义（Schema 管不了的部分）
    def test_empty_text_and_empty_attachments_is_rejected(self):
        body = make_body()
        body["input"] = {"text": "   ", "attachmentIds": []}
        with self.assertRaises(ProtocolError) as caught:
            self.parse(body)
        self.assertEqual(caught.exception.code, "INVALID_ARGUMENT")

    def test_self_parent_is_rejected(self):
        body = make_body()
        body["task"]["parentTaskId"] = body["task"]["id"]
        with self.assertRaises(ProtocolError) as caught:
            self.parse(body)
        self.assertIn("parentTaskId", caught.exception.message)

    def test_bad_reason_enum_is_rejected(self):
        body = make_body()
        body["context"]["reason"] = "WHATEVER"
        with self.assertRaises(ProtocolError):
            self.parse(body)

    def test_bad_datetime_is_rejected(self):
        body = make_body()
        body["task"]["deadlineAt"] = "2026/10/29 02:01"
        with self.assertRaises(ProtocolError):
            self.parse(body)


class ControlSettleTest(unittest.TestCase):
    """Control 的四字段联动 —— v3 报错最多的地方。"""

    def test_complete_needs_outcome(self):
        control = settle_control(NEXT_COMPLETE, outcome=OUTCOME_SUCCEEDED)
        self.assertEqual(control["outcome"], OUTCOME_SUCCEEDED)
        self.assertIsNone(control["inputRequest"])
        with self.assertRaises(ProtocolError):
            settle_control(NEXT_COMPLETE)

    def test_non_complete_must_have_null_outcome(self):
        for next_step in (NEXT_WAIT_INPUT, NEXT_WAIT_DEPENDENCIES, NEXT_WAIT_CONFIRMATION):
            with self.subTest(next=next_step):
                with self.assertRaises(ProtocolError):
                    settle_control(next_step, outcome=OUTCOME_SUCCEEDED,
                                   input_request={"inputRequestId": str(uuid.uuid4()),
                                                  "question": "q", "requiredFields": ["f"],
                                                  "options": [], "allowFreeText": True},
                                   dependency_task_ids=["t-1"])

    def test_wait_input_needs_question(self):
        with self.assertRaises(ProtocolError):
            settle_control(NEXT_WAIT_INPUT)
        question = new_input_request("想学什么？", ["kind"])
        control = settle_control(NEXT_WAIT_INPUT, input_request=question)
        self.assertEqual(control["inputRequest"]["inputRequestId"], question["inputRequestId"])

    def test_wait_dependencies_needs_at_least_one(self):
        with self.assertRaises(ProtocolError):
            settle_control(NEXT_WAIT_DEPENDENCIES, dependency_task_ids=[])
        control = settle_control(NEXT_WAIT_DEPENDENCIES, dependency_task_ids=["child-9"])
        self.assertEqual(control["dependencyTaskIds"], ["child-9"])

    def test_complete_cannot_carry_extra_payload(self):
        with self.assertRaises(ProtocolError):
            settle_control(NEXT_COMPLETE, outcome=OUTCOME_SUCCEEDED,
                           input_request=new_input_request("q", ["f"]))

    def test_unknown_next_is_rejected(self):
        for bad in ("ROUTE_INPUT", "DONE", ""):
            with self.subTest(next=bad):
                with self.assertRaises(ProtocolError):
                    settle_control(bad)


class QuestionProposalTest(unittest.TestCase):
    """问题草案 —— 官方专门有两条 invalidCase 说这个。"""

    def test_generates_uuid_v4(self):
        question = new_input_request("你想参加哪类文化活动？", ["activityKind"])
        parsed = uuid.UUID(question["inputRequestId"])
        self.assertEqual(parsed.version, 4)

    def test_each_question_gets_its_own_id(self):
        ids = {new_input_request("q", ["f"])["inputRequestId"] for _ in range(50)}
        self.assertEqual(len(ids), 50, "50 次生成不能撞 ID")

    def test_matches_official_pattern(self):
        root = load_schema()
        question = new_input_request("选一个", ["kind"],
                                     options=[{"id": "a", "label": "剪纸", "value": "a"}])
        schema_check.validate(question, root["definitions"]["QuestionProposal"], root)

    def test_rejects_empty_question_and_fields(self):
        with self.assertRaises(ProtocolError):
            new_input_request("  ", ["f"])
        with self.assertRaises(ProtocolError):
            new_input_request("q", [])
        with self.assertRaises(ProtocolError):
            new_input_request("q", ["f"] * 11)

    def test_rejects_broken_option(self):
        with self.assertRaises(ProtocolError) as caught:
            new_input_request("q", ["f"], options=[{"id": "a"}])
        self.assertIn("label", caught.exception.message)

    def test_relay_keeps_global_id(self):
        """转呈子问题时 ID 必须原样保留，否则老人的答案回不到原来的任务。"""
        pending = {"ownerTaskId": "child-001",
                   "inputRequestId": "8b49d90e-5ea8-4d2d-a855-5f2b4d9c0a11",
                   "version": 7, "question": "你想参加哪类文化活动？",
                   "requiredFields": ["activityKind"],
                   "options": [{"id": "handcraft", "label": "手工体验", "value": "handcraft"}],
                   "allowFreeText": True}
        relayed = relay_question(pending)
        self.assertEqual(relayed["inputRequestId"], pending["inputRequestId"])
        self.assertNotIn("ownerTaskId", relayed)
        self.assertNotIn("version", relayed)

        root = load_schema()
        schema_check.validate(relayed, root["definitions"]["QuestionProposal"], root)


class ResponseBuildingTest(unittest.TestCase):
    """吐得出去。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.root = load_schema()
        cls.inv = parse_invocation(make_body(), root_schema=cls.root)

    def build(self, **kwargs):
        base = {"intent": "culture", "domains": ["culture"],
                "reply_text": "给您找了个剪纸班。",
                "next_step": NEXT_COMPLETE, "outcome": OUTCOME_SUCCEEDED,
                "root_schema": self.root}
        base.update(kwargs)
        return build_response(self.inv, **base)

    def test_output_passes_official_schema(self):
        response = self.build()
        schema_check.validate(response, self.root["definitions"]["AgentResponse"], self.root)
        self.assertEqual(response["code"], "OK")

    def test_echoes_identity_fields(self):
        data = self.build()["data"]
        self.assertEqual(data["conversationId"], "conv-001")
        self.assertEqual(data["messageId"], "msg-001")
        self.assertEqual(data["taskId"], "child-002")
        self.assertEqual(data["invocationId"], "invoke-child-002")
        self.assertEqual(data["baseTaskVersion"], 3)

    def test_audio_url_is_always_null(self):
        """v3 把 audioUrl 写死成 null —— 语音合成不是 A3 的事。"""
        self.assertIsNone(self.build()["data"]["reply"]["audioUrl"])

    def test_speech_rate_clamped(self):
        self.assertIsNone(self.build(speech_rate=0.5)["data"]["reply"]["audioUrl"])
        for bad in (0.4, 1.6, -1):
            with self.subTest(rate=bad):
                with self.assertRaises(ProtocolError):
                    self.build(speech_rate=bad)

    def test_empty_reply_is_rejected(self):
        for bad in ("", "   "):
            with self.subTest(text=bad):
                with self.assertRaises(ProtocolError):
                    self.build(reply_text=bad)

    def test_unknown_intent_or_domain_is_rejected(self):
        with self.assertRaises(ProtocolError):
            self.build(intent="cooking")
        with self.assertRaises(ProtocolError):
            self.build(domains=["culture", "cooking"])

    def test_domains_deduped_and_kept_in_order(self):
        data = self.build(domains=["culture", "tourism", "culture"])["data"]
        self.assertEqual(data["domains"], ["culture", "tourism"])

    def test_wait_confirmation_needs_ids(self):
        with self.assertRaises(ProtocolError) as caught:
            self.build(next_step=NEXT_WAIT_CONFIRMATION, outcome=None)
        self.assertIn("confirmationIds", caught.exception.message)

        data = self.build(next_step=NEXT_WAIT_CONFIRMATION, outcome=None,
                          confirmation_ids=["confirm-001"])["data"]
        self.assertEqual(data["confirmationIds"], ["confirm-001"])

    def test_handoff_shape(self):
        handoff = build_handoff("scenic", "老人需要景区工作人员带路")
        data = self.build(handoff=handoff)["data"]
        self.assertEqual(data["handoff"]["to"], "scenic")
        with self.assertRaises(ProtocolError):
            build_handoff("police", "理由")
        with self.assertRaises(ProtocolError):
            build_handoff("scenic", "  ")


class UsedMemoryRefsTest(unittest.TestCase):
    """记忆引用不许瞎写 —— 那等于绕过 P2 的授权。"""

    AVAILABLE = [
        {"memoryId": "memory-001", "version": 2},
        {"memoryId": "memory-002", "version": 1},
    ]

    def test_valid_refs_pass(self):
        out = verify_used_memory_refs([{"memoryId": "memory-001", "version": 2}], self.AVAILABLE)
        self.assertEqual(out, [{"memoryId": "memory-001", "version": 2}])

    def test_fabricated_memory_is_forbidden(self):
        with self.assertRaises(ProtocolError) as caught:
            verify_used_memory_refs([{"memoryId": "memory-999", "version": 1}], self.AVAILABLE)
        self.assertEqual(caught.exception.status, 403)
        self.assertEqual(caught.exception.code, "FORBIDDEN")

    def test_stale_version_is_conflict(self):
        with self.assertRaises(ProtocolError) as caught:
            verify_used_memory_refs([{"memoryId": "memory-001", "version": 1}], self.AVAILABLE)
        self.assertEqual(caught.exception.code, "STALE_VERSION")

    def test_no_available_means_no_refs_allowed(self):
        with self.assertRaises(ProtocolError):
            verify_used_memory_refs([{"memoryId": "memory-001", "version": 2}], [])

    def test_duplicates_collapsed(self):
        ref = {"memoryId": "memory-001", "version": 2}
        self.assertEqual(len(verify_used_memory_refs([ref, dict(ref)], self.AVAILABLE)), 1)

    def test_cap_is_twenty(self):
        many = [{"memoryId": "memory-001", "version": 2}] * 21
        with self.assertRaises(ProtocolError):
            verify_used_memory_refs(many, self.AVAILABLE)

    def test_malformed_entry_is_rejected(self):
        for bad in ([{"memoryId": "memory-001"}],
                    [{"memoryId": "", "version": 1}],
                    [{"memoryId": "memory-001", "version": 0}],
                    [{"memoryId": "memory-001", "version": True}],
                    ["memory-001"]):
            with self.subTest(ref=bad):
                with self.assertRaises(ProtocolError):
                    verify_used_memory_refs(bad, self.AVAILABLE)


class ErrorResponseTest(unittest.TestCase):
    """错得明白。"""

    def test_all_sixteen_codes_have_status(self):
        self.assertEqual(len(ERROR_STATUS), 16)
        self.assertEqual(set(ERROR_STATUS), {
            "INVALID_ARGUMENT", "FORBIDDEN", "NOT_FOUND", "CONFLICT",
            "QUESTION_NOT_PENDING", "STALE_VERSION", "TASK_NOT_RUNNABLE",
            "UPSTREAM_ERROR", "UPSTREAM_TIMEOUT", "CAPABILITY_UNAVAILABLE",
            "UNAUTHORIZED", "UNSUPPORTED_PROTOCOL_VERSION", "RATE_LIMITED",
            "CONFIRMATION_REQUIRED", "CONFIRMATION_EXPIRED", "INTERNAL_ERROR",
        })

    def test_codes_match_official_schema(self):
        root = load_schema()
        official = set(root["definitions"]["ErrorResponse"]["properties"]["code"]["enum"])
        self.assertEqual(set(ERROR_STATUS), official)

    def test_error_body_has_null_data(self):
        status, body = error_response("CAPABILITY_UNAVAILABLE", "检索服务不可用")
        self.assertEqual(status, 503)
        self.assertIsNone(body["data"])
        root = load_schema()
        schema_check.validate(body, root["definitions"]["ErrorResponse"], root)

    def test_unknown_code_is_rejected(self):
        with self.assertRaises(ProtocolError):
            error_response("SOMETHING_ELSE", "x")

    def test_blank_message_gets_a_default(self):
        _, body = error_response("CONFLICT", "   ")
        self.assertTrue(body["message"])

    def test_exception_mapping_never_leaks_details(self):
        status, body = from_exception(RuntimeError("数据库密码是 xxx"))
        self.assertEqual(status, 500)
        self.assertEqual(body["code"], "INTERNAL_ERROR")
        self.assertNotIn("密码", body["message"])

    def test_protocol_error_keeps_its_code(self):
        status, body = from_exception(ProtocolError("FORBIDDEN", "越权"))
        self.assertEqual((status, body["code"]), (403, "FORBIDDEN"))


class OfflineReplayTest(unittest.TestCase):
    """用官方 38 + 14 份样例离线回放 —— 不连 P2 也能证明合规。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.root = load_schema()
        cls.examples = load_examples()

    def test_all_valid_cases_pass_schema(self):
        for case in self.examples["cases"]:
            with self.subTest(case=case["name"]):
                schema_check.validate(case["body"],
                                      self.root["definitions"][case["schema"]], self.root)

    def test_all_invalid_cases_are_rejected(self):
        for case in self.examples["invalidCases"]:
            with self.subTest(case=case["name"]):
                self.assertFalse(
                    schema_check.is_valid(case["body"],
                                          self.root["definitions"][case["schema"]], self.root),
                    f"{case['name']} 本该被拒，却通过了")

    def test_every_invocation_request_parses(self):
        count = 0
        for case in self.examples["cases"]:
            if case["schema"] != "InvocationRequest":
                continue
            with self.subTest(case=case["name"]):
                inv = parse_invocation(copy.deepcopy(case["body"]), root_schema=self.root)
                self.assertIsInstance(inv, Invocation)
                count += 1
        self.assertEqual(count, 7)

    def test_a3_memory_review_example_passes_schema(self):
        """样例 20 就是 A3 交给 A1 的记忆审核建议，必须能过。"""
        case = next(c for c in self.examples["cases"] if c["schema"] == "MemoryReview")
        schema_check.validate(case["body"], self.root["definitions"]["MemoryReview"], self.root)
        self.assertEqual(case["body"]["recommendation"], "ADD")

    def test_a3_delegation_example_targets_a3(self):
        """样例 30 是 A1 委派给 A3，targetAgent 必须是 a3。"""
        case = next(c for c in self.examples["cases"] if c["schema"] == "DelegationRequest")
        self.assertEqual(case["body"]["input"]["targetAgent"], "a3")
        self.assertEqual(case["body"]["input"]["domain"], "culture")

    def test_roundtrip_build_response_from_real_request(self):
        case = next(c for c in self.examples["cases"]
                    if c["schema"] == "InvocationRequest")
        inv = parse_invocation(copy.deepcopy(case["body"]), root_schema=self.root)
        response = build_response(
            inv, intent="culture", domains=["culture"], reply_text="剪纸班在活动室。",
            next_step=NEXT_COMPLETE, outcome=OUTCOME_FAILED,
            root_schema=self.root)
        schema_check.validate(response, self.root["definitions"]["AgentResponse"], self.root)
        self.assertEqual(response["data"]["baseTaskVersion"], inv.task_version)


class SchemaCheckSelfTest(unittest.TestCase):
    """校验器本身也要被验 —— 太松的话上面那些「全过」就没意义。"""
    def test_type_errors_caught(self):
        with self.assertRaises(schema_check.SchemaError):
            schema_check.validate("x", {"type": "integer"})
        with self.assertRaises(schema_check.SchemaError):
            schema_check.validate(True, {"type": "integer"})

    def test_const_and_enum(self):
        with self.assertRaises(schema_check.SchemaError):
            schema_check.validate("2.0", {"const": "3.0"})
        with self.assertRaises(schema_check.SchemaError):
            schema_check.validate("x", {"enum": ["a", "b"]})

    def test_additional_properties_false(self):
        schema = {"type": "object", "properties": {"a": {"type": "string"}},
                  "additionalProperties": False}
        with self.assertRaises(schema_check.SchemaError):
            schema_check.validate({"a": "1", "b": "2"}, schema)

    def test_datetime_format(self):
        schema = {"type": "string", "format": "date-time"}
        for good in ("2026-10-29T02:01:00Z", "2026-10-29T02:01:00.123Z",
                     "2026-10-29T10:01:00+08:00"):
            with self.subTest(value=good):
                schema_check.validate(good, schema)
        for bad in ("2026/10/29", "2026-10-29", "2026-10-29 02:01:00", "昨天"):
            with self.subTest(value=bad):
                with self.assertRaises(schema_check.SchemaError):
                    schema_check.validate(bad, schema)

    def test_if_then_else(self):
        schema = {"type": "object", "properties": {"next": {"type": "string"},
                                                   "outcome": {"type": ["string", "null"]}},
                  "if": {"properties": {"next": {"const": "COMPLETE"}}},
                  "then": {"properties": {"outcome": {"type": "string"}}},
                  "else": {"properties": {"outcome": {"type": "null"}}}}
        schema_check.validate({"next": "COMPLETE", "outcome": "SUCCEEDED"}, schema)
        schema_check.validate({"next": "WAIT_INPUT", "outcome": None}, schema)
        with self.assertRaises(schema_check.SchemaError):
            schema_check.validate({"next": "COMPLETE", "outcome": None}, schema)
        with self.assertRaises(schema_check.SchemaError):
            schema_check.validate({"next": "WAIT_INPUT", "outcome": "SUCCEEDED"}, schema)

    def test_missing_required_lists_what_is_there(self):
        with self.assertRaises(schema_check.SchemaError) as caught:
            schema_check.validate({"a": 1},
                                  {"type": "object", "properties": {"a": {}, "b": {}},
                                   "required": ["b"]})
        self.assertIn("b", caught.exception.message)

    def test_domains_constant_matches_schema(self):
        root = load_schema()
        official = tuple(root["definitions"]["AgentData"]["properties"]["intent"]["enum"])
        self.assertEqual(DOMAINS, official)


class SchemaSyncTest(unittest.TestCase):
    """仓库里的 Schema 副本不能和官方包跑偏。

    为什么要有这一条：副本的好处是队友 clone 就能跑，坏处是**会过期**。
    一旦 P2 悄悄改了 Schema，我们还在用旧的校验，测试全绿但报文全错。
    所以只要官方包在本地，就逐字节比一次；不在就跳过（不误报失败）。
    """

    VENDORED = os.path.join(ROOT, "schemas")
    OFFICIAL = os.path.join(ROOT, "..", "_v3开发包", "agent-v3-r3")

    def test_vendored_copy_exists(self):
        for name in ("control.schema.json", "examples.json"):
            with self.subTest(file=name):
                self.assertTrue(os.path.exists(os.path.join(self.VENDORED, name)),
                                f"仓库里缺少 schemas/{name}，队友 clone 后无法自校")

    def test_vendored_matches_official(self):
        import hashlib

        if not os.path.exists(os.path.join(self.OFFICIAL, "control.schema.json")):
            self.skipTest("本地没有官方开发包，跳过比对（CI/队友机器上属正常）")

        for name in ("control.schema.json", "examples.json"):
            with self.subTest(file=name):
                with open(os.path.join(self.VENDORED, name), "rb") as handle:
                    vendored = hashlib.sha256(handle.read()).hexdigest()
                with open(os.path.join(self.OFFICIAL, name), "rb") as handle:
                    official = hashlib.sha256(handle.read()).hexdigest()
                self.assertEqual(vendored, official,
                                 f"schemas/{name} 与官方包不一致：P2 改过协议了，请重新复制并核对")

    def test_schema_is_actually_found(self):
        """防「测试全绿其实一条没跑」—— 尺子必须在。"""
        self.assertTrue(v3_messages.schema_available(), "找不到 control.schema.json")
        self.assertIsNotNone(v3_messages.schema_dir())


if __name__ == "__main__":
    unittest.main(verbosity=2)
