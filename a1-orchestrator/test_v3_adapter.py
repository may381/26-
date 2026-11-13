import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from v3_adapter import handle, _tourism_source, _itinerary_draft
from local_domains import DomainError


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.request = {
            "protocolVersion": "3.0", "userId": "test-user", "conversationId": "conv-test", "messageId": "msg-test",
            "task": {"id": "root-test", "parentTaskId": None, "version": 2, "invocationId": "invoke-test", "deadlineAt": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()},
            "input": {"text": "想学剪纸，别太远", "attachmentIds": []},
            "context": {"reason": "USER_MESSAGE", "history": []}
        }
        self.planner = Mock(return_value={"decision": "ASK", "reply": "在哪座城市？", "domains": ["culture"], "steps": [], "memoryCandidate": None})

    def test_question_has_program_id_but_no_server_owned_fields(self):
        result = handle(self.request, self.planner)
        self.assertEqual(result["data"]["taskId"], "root-test")
        self.assertEqual(result["data"]["baseTaskVersion"], 2)
        question = result["data"]["control"]["inputRequest"]
        self.assertEqual(uuid.UUID(question["inputRequestId"]).version, 4)
        self.assertNotIn("version", question)
        self.assertNotIn("ownerTaskId", question)

    def test_answer_is_not_duplicated_into_history(self):
        self.request["context"].update(reason="INPUT_PROVIDED", inputResponse={"text": "长沙", "responseTo": {
            "ownerTaskId": "root-test", "inputRequestId": str(uuid.uuid4()), "version": 1, "selectedOptionId": None}})
        handle(self.request, self.planner)
        self.assertEqual(self.planner.call_args[0][0], "长沙")
        # 当前消息本身就是回答，不能再作为一条历史重复回灌给模型。
        self.assertEqual(self.planner.call_args[0][1], [])

    def test_trip_shortcut_does_not_answer_pending_days_or_call_model(self):
        self.request['context'].update(reason='INPUT_PROVIDED', inputResponse={
            'text': '帮我规划出行', 'question': {'question': '目的地是长沙。请问您计划去几天？'},
            'responseTo': {'ownerTaskId': 'root-test', 'inputRequestId': str(uuid.uuid4()), 'version': 1}})
        result = handle(self.request, self.planner)
        self.assertEqual(result['data']['control']['next'], 'WAIT_INPUT')
        self.assertIn('当前还需要您补充', result['data']['reply']['text'])
        self.assertIn('几天', result['data']['reply']['text'])
        self.planner.assert_not_called()

    def test_places_are_intermediate_when_itinerary_requested(self):
        self.request['input']['text'] = '帮我规划长沙一天的行程，少走路'
        self.planner.return_value = {'decision': 'PLAN', 'reply': '查询', 'domains': ['tourism'],
            'steps': [{'id': 's1', 'agent': 'a1', 'domain': 'tourism', 'goal': '查询长沙行程', 'dependsOn': []}],
            'memoryCandidate': None, 'location': '长沙'}
        domain = Mock()
        domain.tourism.side_effect = DomainError('返回演示资料')
        domain.places.return_value = [{'name': '橘子洲', 'address': '长沙', 'location': '112.9,28.1'}]
        result = handle(self.request, self.planner, domain_client=domain)
        control = result['data']['control']
        self.assertEqual(control['next'], 'WAIT_INPUT')
        self.assertIsNone(control['outcome'])
        self.assertEqual(control['inputRequest']['requiredFields'], ['walkingTolerance'])
        self.assertEqual(result['data']['results'][0]['payload']['itineraryDraft'][0]['place']['name'], '橘子洲')
        self.assertIn('行程尚未完成', result['data']['reply']['text'])

    def test_five_day_draft_uses_only_queried_places_and_keeps_rest_days(self):
        places = {'places': [{'name': '地点甲'}, {'name': '地点甲'}, {'name': '地点乙'}]}
        result = _itinerary_draft(places, '北京', '只规划北京当地5天，少走路', [])
        self.assertEqual(len(result['days']), 5)
        self.assertEqual(result['days'][1]['place']['name'], '地点乙')
        self.assertIsNone(result['days'][2]['place'])
        self.assertIn('第5天', result['text'])
        self.assertIn('未计算步行路线', result['text'])
        self.assertFalse(any(day['verifiedRoute'] for day in result['days']))

    def test_draft_uses_latest_duration_and_never_assistant_claims(self):
        history = [{'role': 'user', 'content': '规划北京3天'},
                   {'role': 'assistant', 'content': '我给您安排10天'}]
        result = _itinerary_draft({'places': [{'name': '地点甲'}]}, '北京', '改为五天', history)
        self.assertEqual(len(result['days']), 5)

    def test_nearby_places_are_choices_not_separate_days(self):
        result = _itinerary_draft({'places': [
            {'name': '地点甲', 'location': '116.39,39.90'},
            {'name': '地点乙', 'location': '116.391,39.901'}]}, '北京', '规划北京5天', [])
        self.assertIn('建议择一', result['text'])
        self.assertIsNone(result['days'][1]['place'])
        self.assertIn('步行通道未核实', result['text'])

    def test_known_walking_tolerance_is_not_asked_again(self):
        result = _itinerary_draft({'places': [{'name': '地点甲'}]}, '北京',
                                  '每次10分钟需要休息', [{'role': 'user', 'content': '规划北京5天'}])
        self.assertEqual(result['requiredField'], 'selectedPlace')
        self.assertNotIn('多久需要休息', result['question'])
        self.assertIn('10分钟', result['text'])

    def test_ask_summary_never_claims_domain_execution(self):
        result = handle(self.request, self.planner)
        self.assertIn('处理记录', result['data']['reply']['text'])
        self.assertNotIn('旅游查询已返回', result['data']['reply']['text'])
        self.assertEqual(result['data']['results'], [])

    def test_answer_hint_carries_pending_question(self):
        question = "请问希望在哪座城市或哪个地点附近查找？"
        pending = {"question": question, "options": [], "inputRequestId": str(uuid.uuid4()),
                   "ownerTaskId": "root-test", "version": 1,
                   "requiredFields": ["clarification"], "allowFreeText": True}
        self.request["context"].update(reason="INPUT_PROVIDED", inputResponse={
            "text": "长沙", "question": pending,
            "responseTo": {"ownerTaskId": "root-test",
                           "inputRequestId": pending["inputRequestId"], "version": 1}})
        calls = []

        def planner(text, history, deadline=None, hint=None):
            calls.append({"text": text, "history": history, "hint": hint})
            return {"decision": "ASK", "reply": "好的", "domains": ["tourism"],
                    "steps": [], "memoryCandidate": None}

        self.assertEqual(handle(self.request, planner)["code"], "OK")
        self.assertEqual(calls[0]["text"], "长沙")
        # 只回答了一个城市时，把上一轮问题作为本轮约束传入，避免被当成旧行程出发地。
        self.assertIn(question, calls[0]["hint"])
        self.assertIn("一次只能执行一个步骤", calls[0]["hint"])

    def test_resumed_trip_discards_older_trip_history(self):
        self.request['context']['history'] = [
            {'role': 'user', 'text': '我想去杭州'},
            {'role': 'assistant', 'text': '玩几天？'},
            {'role': 'user', 'text': '我想安排一次旅游'},
            {'role': 'assistant', 'text': '您想去哪个城市旅游？'}]
        self.request['context'].update(reason='INPUT_PROVIDED', inputResponse={
            'text': '长沙市，市中心附近',
            'question': {'question': '您想去哪个城市旅游？'},
            'responseTo': {'ownerTaskId': 'root-test',
                           'inputRequestId': str(uuid.uuid4()), 'version': 1}})
        handle(self.request, self.planner)
        self.assertNotIn('杭州', str(self.planner.call_args[0][1]))
        self.assertIn('我想安排一次旅游', str(self.planner.call_args[0][1]))

    def test_new_trip_request_hint_blocks_stale_destination(self):
        calls = []

        def planner(text, history, deadline=None, hint=None):
            calls.append(hint or "")
            return {"decision": "ASK", "reply": "请问您想去哪个城市？", "domains": ["tourism"],
                    "steps": [], "memoryCandidate": None}

        self.request["input"]["text"] = "帮我规划出行"
        self.assertEqual(handle(self.request, planner)["code"], "OK")
        self.assertIn("新的出行请求", calls[0])
        self.assertIn("不得据此询问出发地", calls[0])

    def test_multi_step_a1_plan_is_retried_then_asks_instead_of_failing(self):
        multi = {"decision": "PLAN", "reply": "准备多步", "domains": ["tourism"],
                 "steps": [{"id": "s1", "agent": "a1", "domain": "tourism", "goal": "查交通", "dependsOn": []},
                           {"id": "s2", "agent": "a1", "domain": "tourism", "goal": "排路线", "dependsOn": ["s1"]}],
                 "memoryCandidate": None, "location": "长沙"}
        calls = []

        def planner(text, history, deadline=None, hint=None):
            calls.append(hint or "")
            return multi if len(calls) == 1 else {"decision": "ASK", "reply": "请先说明一项",
                                                  "domains": ["tourism"], "steps": [],
                                                  "memoryCandidate": None}

        result = handle(self.request, planner)
        self.assertEqual(result["code"], "OK")
        self.assertEqual(len(calls), 2)
        self.assertIn("步骤纠正", calls[1])
        self.assertEqual(result["data"]["control"]["next"], "WAIT_INPUT")

    def test_multi_step_a1_plan_without_retry_budget_asks_user(self):
        self.planner.return_value = {"decision": "PLAN", "reply": "准备多步", "domains": ["tourism"],
            "steps": [{"id": "s1", "agent": "a1", "domain": "tourism", "goal": "查交通", "dependsOn": []},
                      {"id": "s2", "agent": "a1", "domain": "tourism", "goal": "排路线", "dependsOn": ["s1"]}],
            "memoryCandidate": None, "location": "长沙"}
        result = handle(self.request, self.planner)
        self.assertEqual(result["code"], "OK")
        self.assertEqual(result["data"]["control"]["next"], "WAIT_INPUT")
        self.assertIn("一次只能完成一项", result["data"]["reply"]["text"])

    def test_free_text_answer_without_selected_option_is_accepted(self):
        # P2 的自由文本回答只带 ownerTaskId/inputRequestId/version。
        self.request["context"].update(reason="INPUT_PROVIDED", inputResponse={"text": "长沙", "responseTo": {
            "ownerTaskId": "root-test", "inputRequestId": str(uuid.uuid4()), "version": 1}})
        result = handle(self.request, self.planner)
        self.assertEqual(result["code"], "OK")
        self.assertEqual(self.planner.call_args[0][0], "长沙")

    def test_expired_does_not_call_model(self):
        self.request["task"]["deadlineAt"] = "2020-01-01T00:00:00Z"
        self.assertEqual(handle(self.request, self.planner)["code"], "UPSTREAM_TIMEOUT")
        self.planner.assert_not_called()

    def test_invalid_nested_container_rejected_before_model(self):
        for key in ("task", "context", "input"):
            packet = dict(self.request)
            packet[key] = []
            self.assertEqual(handle(packet, self.planner)["code"], "INVALID_ARGUMENT")
        self.planner.assert_not_called()

    def test_child_answer_must_not_resume_root_plan(self):
        self.request["context"].update(reason="INPUT_PROVIDED", inputResponse={"text": "长沙", "responseTo": {
            "ownerTaskId": "child-test", "inputRequestId": str(uuid.uuid4()), "version": 1, "selectedOptionId": None}})
        self.assertEqual(handle(self.request, self.planner)["code"], "CAPABILITY_UNAVAILABLE")
        self.planner.assert_not_called()

    def test_unknown_recovery_does_not_reexecute(self):
        self.request["context"]["reason"] = "RECOVERY"
        self.request["context"]["actionLedger"]=[{"stepId":"s1","actionId":"a1","tool":"route.save","argsDigest":"x",
            "confirmationId":None,"executionStatus":"UNKNOWN","effectId":None,"businessRef":None,
            "externalStatus":None,"lastError":None,"retryPolicy":"RECONCILE_FIRST"}]
        self.assertEqual(handle(self.request, self.planner)["code"], "UPSTREAM_ERROR")
        self.planner.assert_not_called()

    def test_plan_does_not_invent_child_ids(self):
        self.planner.return_value["decision"] = "PLAN"
        self.assertEqual(handle(self.request, self.planner)["code"], "CAPABILITY_UNAVAILABLE")

    def test_plan_returns_real_child_ids_from_executor(self):
        self.planner.return_value = {"decision": "PLAN", "reply": "准备协作", "domains": ["culture"],
            "steps": [{"id": "s1", "agent": "a3", "domain": "culture", "goal": "查询剪纸课程", "dependsOn": []}],
            "memoryCandidate": None, "location": "长沙"}
        executor = Mock()
        executor.delegate_children.return_value = [{"childTaskId": "child-real-1", "status": "QUEUED"}]
        result = handle(self.request, self.planner, executor)
        self.assertEqual(result["code"], "OK")
        self.assertEqual(result["data"]["control"], {
            "next": "WAIT_DEPENDENCIES", "outcome": None,
            "dependencyTaskIds": ["child-real-1"], "inputRequest": None})
        executor.delegate_children.assert_called_once()

    def test_a1_tourism_plan_calls_real_domain_client_and_returns_v3_result(self):
        self.planner.return_value = {"decision": "PLAN", "reply": "准备查询", "domains": ["tourism"],
            "steps": [{"id": "s1", "agent": "a1", "domain": "tourism",
                       "goal": "查询西湖慢行建议", "dependsOn": []}],
            "memoryCandidate": None, "location": "杭州"}
        domain = Mock()
        domain.tourism.return_value = {"text": "西湖慢行建议已由8091返回。", "sources": [{"source": "AMAP"}]}
        self.request["input"]["text"] = "请介绍杭州西湖适合慢慢散步的地方"
        result = handle(self.request, self.planner, domain_client=domain)
        self.assertEqual(result["code"], "OK")
        self.assertEqual(result["data"]["control"]["outcome"], "SUCCEEDED")
        self.assertEqual(result["data"]["results"][0]["type"], "TOURISM_ADVICE")
        self.assertEqual(result["data"]["results"][0]["availability"], "REAL")
        self.assertIn("8091", result["data"]["reply"]["text"])
        domain.tourism.assert_called_once_with(self.request["input"]["text"], location="杭州")

    def test_question_carries_planner_options(self):
        self.planner.return_value = {"decision": "ASK", "reply": "您打算哪天出发？", "domains": ["tourism"],
            "steps": [], "memoryCandidate": None,
            "options": [{"id": "today", "label": "今天", "value": "今天"},
                        {"id": "weekend", "label": "周末", "value": "周末"}]}
        result = handle(self.request, self.planner)
        self.assertEqual(result["code"], "OK")
        question = result["data"]["control"]["inputRequest"]
        self.assertEqual([option["id"] for option in question["options"]], ["today", "weekend"])
        self.assertTrue(question["allowFreeText"])

    def test_tourism_card_carries_real_places_for_map(self):
        self.planner.return_value = {"decision": "PLAN", "reply": "准备查询", "domains": ["tourism"],
            "steps": [{"id": "s1", "agent": "a1", "domain": "tourism",
                       "goal": "查询西湖慢行建议", "dependsOn": []}],
            "memoryCandidate": None, "location": "杭州"}
        domain = Mock()
        domain.tourism.return_value = {"text": "西湖慢行建议已由8091返回。"}
        domain.places.return_value = [{"name": "西湖", "address": "杭州市西湖区",
                                       "location": "120.155,30.265", "type": "风景名胜"}]
        self.request["input"]["text"] = "我想去杭州西湖，慢慢走"
        result = handle(self.request, self.planner, domain_client=domain)
        card = result["data"]["results"][0]
        self.assertEqual(card["payload"]["places"][0]["name"], "西湖")
        self.assertEqual(card["payload"]["placesSource"]["provider"], "AMAP")
        self.assertEqual(card["availability"], "NEEDS_VERIFICATION")
        domain.places.assert_called_once_with("杭州西湖")

    def test_place_lookup_failure_keeps_tourism_answer(self):
        self.planner.return_value = {"decision": "PLAN", "reply": "准备查询", "domains": ["tourism"],
            "steps": [{"id": "s1", "agent": "a1", "domain": "tourism",
                       "goal": "查询西湖慢行建议", "dependsOn": []}],
            "memoryCandidate": None, "location": "杭州"}
        domain = Mock()
        domain.tourism.return_value = {"text": "西湖慢行建议已由8091返回。"}
        domain.places.side_effect = DomainError("高德暂不可用")
        result = handle(self.request, self.planner, domain_client=domain)
        self.assertEqual(result["code"], "OK")
        card = result["data"]["results"][0]
        self.assertNotIn("places", card["payload"])

    def test_tourism_source_does_not_replay_unrelated_old_city(self):
        history = [{"role": "user", "content": "我想去杭州玩三天"},
                   {"role": "assistant", "content": "杭州适合慢慢逛。"}]
        self.assertEqual(_tourism_source("长沙", "长沙", history), "长沙")
        # A clarification still carries the one user sentence that names the city.
        self.assertEqual(_tourism_source(
            "两天", "长沙", [{"role": "user", "content": "我想去长沙玩"}]),
            "我想去长沙玩\n两天")

    def test_city_recommendation_falls_back_to_real_amap_places(self):
        self.planner.return_value = {"decision": "PLAN", "reply": "准备查询", "domains": ["tourism"],
            "steps": [{"id": "s1", "agent": "a1", "domain": "tourism",
                       "goal": "查询长沙适合老人的景点", "dependsOn": []}],
            "memoryCandidate": None, "location": "长沙"}
        domain = Mock()
        domain.tourism.side_effect = DomainError("旅游服务返回演示资料，未取得真实旅游查询结果")
        domain.places.return_value = [{"name": "橘子洲风景名胜区", "address": "湖南省长沙市岳麓区橘子洲头2号",
                                       "location": "112.963081,28.196505", "type": "风景名胜"}]
        self.request["input"]["text"] = "请推荐长沙适合老人、少走路的真实景点"
        result = handle(self.request, self.planner, domain_client=domain)
        self.assertEqual(result["code"], "OK")
        self.assertIn("橘子洲风景名胜区", result["data"]["reply"]["text"])
        card = result["data"]["results"][0]
        self.assertEqual(card["availability"], "REAL")
        self.assertEqual(card["payload"]["places"][0]["name"], "橘子洲风景名胜区")
        # 城市级推荐必须用城市参数查高德，而不是把城市塞进景点 ID 位置。
        domain.places.assert_called_once_with("景点", "长沙")

    def test_bare_city_answer_uses_amap_instead_of_8091_dialogue(self):
        # 用户只回答城市名时，8091 对话接口会返回含糊反问；应直接查高德真实地点。
        self.planner.return_value = {"decision": "PLAN", "reply": "准备查询", "domains": ["tourism"],
            "steps": [{"id": "s1", "agent": "a1", "domain": "tourism",
                       "goal": "查询长沙适合老人的景点", "dependsOn": []}],
            "memoryCandidate": None, "location": "长沙"}
        domain = Mock()
        domain.places.return_value = [{"name": "岳麓山风景名胜区", "address": "湖南省长沙市岳麓区登高路58号",
                                       "location": "112.936104,28.183601", "type": "风景名胜"}]
        self.request["input"]["text"] = "长沙"
        result = handle(self.request, self.planner, domain_client=domain)
        domain.tourism.assert_not_called()
        self.assertEqual(result["code"], "OK")
        self.assertIn("岳麓山风景名胜区", result["data"]["reply"]["text"])
        self.assertEqual(result["data"]["results"][0]["availability"], "REAL")

    def test_tourism_markdown_is_flattened_for_elder_chat(self):
        self.planner.return_value = {"decision": "PLAN", "reply": "准备查询", "domains": ["tourism"],
            "steps": [{"id": "s1", "agent": "a1", "domain": "tourism",
                       "goal": "查询长沙三日行程", "dependsOn": []}],
            "memoryCandidate": None, "location": "长沙"}
        domain = Mock()
        domain.tourism.return_value = {"text": "**第一天**\n*   **交通：** 地铁很方便\n*   **美食：** 微辣",
                                       "sources": [{"provider": "AMAP"}]}
        result = handle(self.request, self.planner, domain_client=domain)
        text = result["data"]["reply"]["text"]
        self.assertNotIn("**", text)
        self.assertNotIn("*   ", text)
        self.assertIn("第一天", text)
        self.assertIn("· 交通： 地铁很方便", text)

    def test_reply_that_forgets_known_destination_is_replaced(self):
        # 已确认长沙后补充「明天出发」，8091 却反问「还没告诉我具体想去哪里」。
        self.planner.return_value = {"decision": "PLAN", "reply": "准备查询", "domains": ["tourism"],
            "steps": [{"id": "s1", "agent": "a1", "domain": "tourism",
                       "goal": "查询长沙三日行程", "dependsOn": []}],
            "memoryCandidate": None, "location": "长沙"}
        domain = Mock()
        domain.tourism.return_value = {
            "text": "不过您还没告诉我具体想去哪里呢？是打算在长沙周边转转，还是去张家界？",
            "sources": [{"provider": "AMAP"}]}
        domain.places.return_value = [{"name": "橘子洲风景名胜区", "address": "湖南省长沙市岳麓区橘子洲头2号",
                                       "location": "112.963081,28.196505", "type": "风景名胜"}]
        self.request["input"]["text"] = "明天出发"
        result = handle(self.request, self.planner, domain_client=domain)
        self.assertEqual(result["code"], "OK")
        reply = result["data"]["reply"]["text"]
        self.assertNotIn("还没告诉我", reply)
        self.assertIn("橘子洲风景名胜区", reply)
        self.assertEqual(result["data"]["results"][0]["availability"], "REAL")

    def test_duration_answer_after_city_still_returns_real_places(self):
        # 「长沙」→「三天」时，8091 仍拿不到景点 ID 而返回演示资料；应回退到高德真实地点。
        self.planner.return_value = {"decision": "PLAN", "reply": "准备查询", "domains": ["tourism"],
            "steps": [{"id": "s1", "agent": "a1", "domain": "tourism",
                       "goal": "查询长沙三日行程", "dependsOn": []}],
            "memoryCandidate": None, "location": "长沙"}
        domain = Mock()
        domain.tourism.side_effect = DomainError("旅游服务返回演示资料，未取得真实旅游查询结果")
        domain.places.return_value = [{"name": "橘子洲风景名胜区", "address": "湖南省长沙市岳麓区橘子洲头2号",
                                       "location": "112.963081,28.196505", "type": "风景名胜"}]
        self.request["input"]["text"] = "三天"
        result = handle(self.request, self.planner, domain_client=domain)
        self.assertEqual(result["code"], "OK")
        self.assertIn("橘子洲风景名胜区", result["data"]["reply"]["text"])
        self.assertEqual(result["data"]["results"][0]["availability"], "REAL")

    def test_no_match_answer_is_replaced_with_real_places(self):
        self.planner.return_value = {"decision": "PLAN", "reply": "准备查询", "domains": ["tourism"],
            "steps": [{"id": "s1", "agent": "a1", "domain": "tourism",
                       "goal": "查询杭州三日行程", "dependsOn": []}],
            "memoryCandidate": None, "location": "杭州"}
        domain = Mock()
        domain.tourism.return_value = {"text": "暂时没有查到与“杭州玩三天”匹配的地点。"}
        domain.places.return_value = [{"name": "西湖", "address": "杭州市西湖区",
                                       "location": "120.155,30.265", "type": "风景名胜"}]
        self.request["input"]["text"] = "我想去杭州玩三天"
        result = handle(self.request, self.planner, domain_client=domain)
        self.assertEqual(result["code"], "OK")
        self.assertIn("西湖", result["data"]["reply"]["text"])
        self.assertEqual(result["data"]["results"][0]["availability"], "REAL")

    def test_a1_domain_failure_never_becomes_success(self):
        self.planner.return_value = {"decision": "PLAN", "reply": "准备查询", "domains": ["tourism"],
            "steps": [{"id": "s1", "agent": "a1", "domain": "tourism",
                       "goal": "查询", "dependsOn": []}], "memoryCandidate": None, "location": None}
        domain = Mock()
        domain.tourism.side_effect = DomainError("8091不可用")
        result = handle(self.request, self.planner, domain_client=domain)
        self.assertEqual(result["code"], "UPSTREAM_ERROR")
        self.assertIsNone(result["data"])

    def test_a1_fraud_plan_returns_verified_completed_result(self):
        self.planner.return_value = {"decision":"PLAN","reply":"准备核实","domains":["fraud"],
            "steps":[{"id":"s1","agent":"a1","domain":"fraud","goal":"核实可疑信息","dependsOn":[]}],
            "memoryCandidate":None,"location":None}
        self.request["input"]["text"]="客服要求我提供验证码办理退款"
        domain=Mock()
        domain.fraud.return_value={"analysisId":"real-test","state":"ACCEPTED"}
        domain.status.return_value={"analysis_id":"real-test","status":"completed","result":{
            "id":"real-test","level":"high","evidence":"要求验证码","advice":["停止操作"]}}
        result=handle(self.request,self.planner,domain_client=domain)
        self.assertEqual(result["code"],"OK")
        self.assertEqual(result["data"]["control"]["outcome"],"SUCCEEDED")
        self.assertEqual(result["data"]["results"][0]["availability"],"REAL")
        domain.fraud.assert_called_once_with(self.request["input"]["text"])

    def test_a1_fraud_pending_is_not_reported_as_completed(self):
        self.planner.return_value = {"decision":"PLAN","reply":"准备核实","domains":["fraud"],
            "steps":[{"id":"s1","agent":"a1","domain":"fraud","goal":"核实可疑信息","dependsOn":[]}],
            "memoryCandidate":None,"location":None}
        domain=Mock()
        domain.fraud.return_value={"analysisId":"real-pending","state":"ACCEPTED"}
        domain.status.return_value={"analysis_id":"real-pending","status":"processing","result":None}
        with patch.dict(os.environ,{"A1_FRAUD_WAIT_SECONDS":"0"}):
            result=handle(self.request,self.planner,domain_client=domain)
        self.assertEqual(result["data"]["control"]["outcome"],"PARTIALLY_SUCCEEDED")
        self.assertEqual(result["data"]["results"][0]["availability"],"NEEDS_VERIFICATION")
        self.assertIn("没有风险结论",result["data"]["reply"]["text"])

    def test_tourism_without_sources_requires_verification(self):
        self.planner.return_value = {"decision": "PLAN", "reply": "准备查询", "domains": ["tourism"],
            "steps": [{"id": "s1", "agent": "a1", "domain": "tourism",
                       "goal": "查询", "dependsOn": []}], "memoryCandidate": None, "location": None}
        domain = Mock()
        domain.tourism.return_value = {"text": "查询结果"}
        result = handle(self.request, self.planner, domain_client=domain)
        card = result["data"]["results"][0]
        self.assertEqual(card["availability"], "NEEDS_VERIFICATION")
        self.assertEqual(card["sources"], [])
        self.assertIn("未提供可核验来源", card["pendingChecks"][0])

    def test_tourism_reply_respects_v3_text_limit(self):
        self.planner.return_value = {"decision": "PLAN", "reply": "准备查询", "domains": ["tourism"],
            "steps": [{"id": "s1", "agent": "a1", "domain": "tourism",
                       "goal": "查询", "dependsOn": []}], "memoryCandidate": None, "location": None}
        domain = Mock()
        domain.tourism.return_value = {"text": "路" * 5000, "sources": [{"source": "AMAP"}]}
        result = handle(self.request, self.planner, domain_client=domain)
        self.assertEqual(len(result["data"]["reply"]["text"]), 4000)
        self.assertTrue(result["data"]["reply"]["text"].endswith("…"))

    def test_child_question_keeps_original_identity(self):
        question = {"inputRequestId": "9f75ab8a-73d4-4e26-909f-2f2e67b95d42", "ownerTaskId": "child-1", "version": 4,
                    "question": "想参加哪类文化活动？", "requiredFields": ["kind"], "options": [], "allowFreeText": True}
        self.request["context"].update(reason="CHILD_INPUT_REQUIRED", pendingInputRequests=[question],
            dependencyResults=[{"taskId": "child-1", "domain": "culture"}])
        result = handle(self.request, self.planner)
        self.assertEqual(result["data"]["control"]["inputRequest"]["inputRequestId"], "9f75ab8a-73d4-4e26-909f-2f2e67b95d42")
        self.assertNotIn("ownerTaskId", result["data"]["control"]["inputRequest"])
        self.planner.assert_not_called()

    def test_children_finished_integrates_without_replanning(self):
        self.request["context"].update(reason="CHILDREN_FINISHED", dependencyResults=[{
            "taskId":"child-1","parentTaskId":"root-test","targetAgent":"a3","domain":"culture",
            "required":True,"version":3,"status":"SUCCEEDED",
            "reply":{"text":"找到一项剪纸课程","speechRate":.8,"audioUrl":None},
            "results":[{"resultId":"result-1","type":"CULTURE","payload":{}}],
            "confirmationIds":[],"effectIds":[],"error":None,
            "completedAt":"2026-11-07T00:00:00Z","inputRequest":None}])
        result=handle(self.request,self.planner)
        self.assertEqual(result["data"]["control"]["outcome"],"SUCCEEDED")
        self.assertEqual(result["data"]["results"][0]["resultId"],"result-1")
        self.assertIn("剪纸课程",result["data"]["reply"]["text"])
        self.planner.assert_not_called()

    def test_child_confirmation_is_presented_without_replanning(self):
        self.request["context"].update(reason="CHILD_CONFIRMATION_REQUIRED",dependencyResults=[{
            "taskId":"child-1","parentTaskId":"root-test","targetAgent":"a2","domain":"care",
            "required":True,"version":3,"status":"WAITING_CONFIRMATION","reply":None,"results":[],
            "confirmationIds":["confirm-real-1"],"effectIds":[],"error":None,"completedAt":None,"inputRequest":None}])
        result=handle(self.request,self.planner)
        self.assertEqual(result["data"]["control"]["next"],"WAIT_CONFIRMATION")
        self.assertEqual(result["data"]["confirmationIds"],["confirm-real-1"])
        self.planner.assert_not_called()

    def test_confirmation_decided_uses_ledger_without_replanning(self):
        self.request["context"].update(reason="CONFIRMATION_DECIDED",confirmationResults=[{
            "confirmationId":"c1","ownerTaskId":"root-test","rootTaskId":"root-test","actionId":"a1",
            "version":2,"state":"EXECUTED","operation":"memory.change","summary":"保存少走路偏好",
            "expiresAt":"2026-11-07T01:00:00Z","actionStatus":"SUCCEEDED","lastError":None,"canRetry":False}],
            actionLedger=[{"stepId":"s1","actionId":"a1","tool":"memory.change","argsDigest":"x",
            "confirmationId":"c1","executionStatus":"SUCCEEDED","effectId":"e1","businessRef":None,
            "externalStatus":None,"lastError":None,"retryPolicy":"NO_RETRY"}])
        result=handle(self.request,self.planner)
        self.assertEqual(result["data"]["control"]["outcome"],"SUCCEEDED")
        self.assertIn("已执行",result["data"]["reply"]["text"])
        self.planner.assert_not_called()


if __name__ == "__main__": unittest.main()
