"""Offline r3 packet adapter. Not an HTTP service or a P2 replacement."""
import argparse
import inspect
import math
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from a1 import ask_model, PlanningError, new_travel_request
from p2_client import P2Client, P2Error
from plan_execution import PlanExecutor
from dependency_integration import integrate_dependencies, collect_child_confirmations
from recovery import integrate_confirmation_decisions, integrate_recovery
from local_domains import DomainClient, DomainError
from v3_reason_graph import route_reason


def failure(code, message):
    return {"code": code, "message": message, "data": None}


def question_id(value):
    try:
        parsed = uuid.UUID(value)
        return parsed.version == 4 and str(parsed) == value.lower()
    except (ValueError, TypeError, AttributeError):
        return False


def _pending_trip_prompt(text, question, history):
    """A generic trip button is not an answer to a concrete pending question."""
    if not isinstance(question, str) or not isinstance(text, str):
        return None
    if text.strip() not in ('帮我规划出行', '帮我安排旅游', '规划出行'):
        return None
    if not (re.search(r'旅游|出行|几天|天数|出发', question)
            or any(line.get('role') == 'user' and re.search(r'旅游|出行|行程', line.get('content', ''))
                   for line in history)):
        return None
    return ('可以继续帮您规划。当前还需要您补充：' + question
            + ' 您也可以直接告诉我新的目的地；如果想重新开始，请点击“新对话”。')


def _tourism_source(text, location, history):
    """Keep the trusted destination but not unrelated old cities.

    8091 requires ``location`` to appear in the submitted text.  A clarification
    such as "两天" does not repeat the city, so add only the most recent user
    message that actually contains the verified location.  Replaying the whole
    conversation let an older city leak into the answer.
    """
    parts = []
    if (isinstance(location, str) and location.strip()
            and isinstance(text, str) and location not in text):
        for line in reversed(history):
            content = line.get('content') if isinstance(line, dict) else None
            if line.get('role') == 'user' and new_travel_request(content):
                parts.append(content.strip())
                break
        for line in reversed(history):
            content = line.get("content") if isinstance(line, dict) else None
            if (line.get("role") == "user" and isinstance(content, str)
                    and location in content):
                if content.strip() not in parts:
                    parts.append(content.strip())
                break
    if isinstance(text, str) and text.strip():
        parts.append(text.strip())
    return "\n".join(parts)[-2000:]


def _plain_text(text):
    """Render domain replies as plain spoken text; the elder chat bubble shows raw characters."""
    if not isinstance(text, str):
        return text
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    text = re.sub(r"(?m)^\s*[*•]\s+", "· ", text)
    text = text.replace("`", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _itinerary_draft(tourism, location, text, history):
    """A conservative scheduling proposal, never an invented route or facility claim."""
    turns = [line.get('content', '') for line in history if line.get('role') == 'user'] + [text]
    source = '\n'.join(turns)
    if not re.search(r'规划|行程|安排.*(?:旅游|出行)|当地.*天', source):
        return None
    days = None
    for turn in reversed(turns):
        matches = re.findall(r'([1-9][0-9]?|[一二两三四五六七八九十])\s*天', turn)
        if matches:
            value = matches[-1]
            days = int(value) if value.isdigit() else {'一':1,'二':2,'两':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10}[value]
            break
    if days is None or not 1 <= days <= 14 or not location:
        return None
    places = []
    seen = set()
    for place in tourism.get('places', []):
        if isinstance(place, dict) and place.get('name') and place['name'] not in seen:
            places.append(place)
            seen.add(place['name'])
    if not places:
        return None
    def nearby(left, right):
        try:
            a, b = [float(v) for v in left['location'].split(',')]
            c, d = [float(v) for v in right['location'].split(',')]
            if not (-180 <= a <= 180 and -180 <= c <= 180 and -90 <= b <= 90 and -90 <= d <= 90):
                return False
            x = math.sin(math.radians(d-b)/2)**2 + math.cos(math.radians(b))*math.cos(math.radians(d))*math.sin(math.radians(c-a)/2)**2
            return 6371000 * 2 * math.asin(math.sqrt(min(1, x))) <= 800
        except (KeyError, ValueError, TypeError, AttributeError):
            return False
    groups = []
    for place in places:
        group = next((g for g in groups if len(g) < 2 and nearby(g[0], place)), None)
        if group is None:
            groups.append([place])
        else:
            group.append(place)
    schedule = []
    lines = [f'{location}{days}天当地游草案（待您确认）',
             '按少走路、多休息的要求，先建议每天最多安排一个主要地点，下午留作休息或机动；往返交通未安排。']
    for index in range(days):
        group = groups[index] if index < len(groups) else []
        place = group[0] if group else None
        activity = ' / '.join(p['name'] for p in group) if group else '休息或机动日，暂不添加未经查询的景点'
        if len(group) > 1:
            activity += '（坐标相近，建议择一；步行通道未核实）'
        schedule.append({'day': index + 1, 'place': place, 'afternoon': '休息或机动', 'verifiedRoute': False})
        lines.append(f'第{index + 1}天：{activity}。下午休息或机动。')
    lines += ['行程尚未完成：这是建议日程，尚未核实各地点是否适合您的体力，也未计算步行路线。',
              '地点名称、地址来自高德查询；开放日期、预约、台阶、座椅、厕所及无障碍设施仍需核实。',
              '为继续细化少走路的安排，您连续步行大约多久需要休息？例如10分钟或20分钟。']
    tolerance = next((m.group(1) for turn in reversed(turns)
                      if (m := re.search(r'(\d{1,3})\s*分钟', turn))), None)
    question = '您连续步行大约多久需要休息？例如10分钟或20分钟。'
    if tolerance:
        lines.pop()
        lines.append(f'已收到您每次步行约{tolerance}分钟的要求；这不代表各地点已满足该要求。')
        question = '您希望先核实哪一个候选地点的步行及休息条件？'
        lines.append(question)
    return {'text': '\n'.join(lines), 'days': schedule, 'question': question,
            'requiredField': 'selectedPlace' if tolerance else 'walkingTolerance'}


def _place_query(location, text):
    """Prefer the phrase the user actually said over a bare city name."""
    if isinstance(text, str) and isinstance(location, str):
        index = text.find(location)
        if index >= 0:
            clause = re.split(r"[，,。；;！!？?\s]", text[index:], 1)[0]
            if len(clause) > len(location):
                return clause[:30]
    return location


def _attach_places(card, client, location, text=None):
    """Add real AMap places so the UI can render a map and place list."""
    if isinstance(card.get("payload"), dict) and card["payload"].get("places"):
        return
    lookup = getattr(client, "places", None)
    if not callable(lookup) or not isinstance(location, str) or not location.strip():
        return
    places = []
    for query in dict.fromkeys((_place_query(location, text), location)):
        try:
            places = lookup(query)
        except DomainError:
            places = []
        if isinstance(places, list) and places:
            location = query
            break
    if not isinstance(places, list) or not places:
        return
    card["payload"]["places"] = places
    card["payload"]["placesSource"] = {"provider": "AMAP", "query": location,
                                       "retrievedAt": datetime.now(timezone.utc).isoformat()}
    if len(card["pendingChecks"]) < 20:
        card["pendingChecks"].append("景点名称、地址与坐标来自高德地图；开放时间与票价仍待官方核实")


RECOMMEND_WORDS = re.compile(r"推荐|景点|好玩|逛逛|旅游|出游|游玩|玩|美食|公园|路线|攻略|行程")

# 8091 只收到「明天出发」这类补充时，会反问「还没告诉我具体想去哪里」，与已确认的
# 目的地自相矛盾。这种回答属于明显的错误上下文，不能原样展示给老人。
DESTINATION_DENIED = re.compile(
    r"还没(?:有)?(?:告诉我|说)(?:具体)?(?:想去|要去|目的地)"
    r"|没(?:有)?告诉(?:我)?(?:具体)?(?:想去|要去)"
    r"|不知道您(?:具体)?(?:想)?(?:去|要)(?:哪|什么城市)")

# 这个外壳每次只执行一个 a1 步骤。把限制写进每轮提示，避免模型把同一个需求
# 拆成「查交通→排路线→找住宿」这类多步计划，然后被适配器整体拒绝。
SINGLE_STEP_HINT = (
    "当前部署一次只能执行一个步骤：若计划中包含 agent=a1 的步骤，steps 必须恰好只有这一项，"
    "dependsOn 必须为空；不要把同一个需求拆成多个 a1 步骤，也不要把 a1 步骤与 a2/a3 步骤写进同一计划。"
)
ANSWER_HINT = (
    "上一轮A1向用户提问「%s」，用户本轮只回答了「%s」。请把这个回答理解为对该提问的回答，"
    "并延续上一轮尚未完成的需求：如果上一轮问的是出发地，就按出发地理解；如果问的是目的地或查找范围，"
    "就按目的地理解。更早对话中的其他城市、天数等细节属于已经结束的旧请求，不要当作本次目的地、"
    "出发地或行程条件，也不要再就旧请求向用户确认；除非用户本轮明确重复。"
)
NEW_TRIP_HINT = (
    "用户本轮发起了新的出行请求。如果本轮没有明确说出目的地城市，必须先问用户想去哪个城市；"
    "历史对话中的城市属于已经结束的旧请求，不得当作本次目的地，也不得据此询问出发地。"
)


def _plan_shape(plan):
    """Structural description only; never log user text or model prose."""
    return [[step.get("agent"), step.get("domain"), len(step.get("dependsOn") or [])]
            for step in plan.get("steps", [])]


def _log_plan_shape(plan, supported):
    """Only unsupported shapes are logged by default; A1_PLAN_TRACE=1 logs every plan."""
    if supported and os.environ.get("A1_PLAN_TRACE") != "1":
        return
    print("[a1] plan-shape supported=%s decision=%s domains=%s steps=%s"
          % (supported, plan.get("decision"), plan.get("domains"), _plan_shape(plan)),
          file=sys.stderr, flush=True)


def _single_step_plan(plan):
    """This shell executes exactly one a1 step, or delegates a plan without a1 steps."""
    if plan.get("decision") != "PLAN":
        return True
    steps = plan.get("steps") or []
    if not any(step.get("agent") == "a1" for step in steps):
        return True
    return (len(steps) == 1 and not steps[0].get("dependsOn")
            and (steps[0].get("agent"), steps[0].get("domain"))
            in (("a1", "tourism"), ("a1", "fraud")))


def _call_planner(planner, text, history, deadline, hint=None):
    """Pass optional extensions only when the planner accepts them (keeps test doubles simple)."""
    parameters = inspect.signature(planner).parameters
    kwargs = {}
    if "deadline" in parameters:
        kwargs["deadline"] = deadline
    if isinstance(hint, str) and hint.strip() and "hint" in parameters:
        kwargs["hint"] = hint
    return planner(text, history, **kwargs)


def _place_recommendation(client, location, text, force=False):
    """Answer city-level recommendation requests with real AMap places.

    8091's conversational endpoint expects a selected spot id in ``context.location``
    and otherwise falls back to its demo park, which A1 must reject.  For a plain
    "recommend places in 长沙" request the real source is 8091's AMap search API.
    ``force`` is used when 8091 already said it has no real answer for this request;
    returning verified AMap places for the trusted city is then the honest fallback.
    """
    lookup = getattr(client, "places", None)
    if not callable(lookup) or not isinstance(location, str) or not location.strip():
        return None
    if not force:
        if not isinstance(text, str) or not RECOMMEND_WORDS.search(text):
            # A bare city is the user's answer to "which city"; still surface real places.
            if not (isinstance(text, str) and text.strip() == location.strip()):
                return None
    keyword = "美食" if "美食" in text else "公园" if "公园" in text else "景点"
    try:
        places = lookup(keyword, location.strip())
    except (DomainError, TypeError):
        return None
    if not isinstance(places, list) or not places:
        return None
    shown = [place for place in places[:6] if isinstance(place, dict) and place.get("name")]
    if not shown:
        return None
    label = "美食" if keyword == "美食" else "地点"
    lines = []
    for index, place in enumerate(shown, 1):
        address = place.get("address")
        lines.append("%d. %s%s" % (index, place["name"], "（%s）" % address if address else ""))
    body = ("高德地图在%s返回的真实%s如下：\n%s\n\n"
            "以上名称、地址和坐标来自高德地图；开放时间、票价和无障碍条件仍待官方核实。"
            % (location.strip(), label, "\n".join(lines)))
    sources = [{"provider": "AMAP", "name": place["name"], "address": place.get("address"),
                "location": place.get("location")} for place in shown]
    return {
        "text": body,
        "sources": sources,
        "pendingChecks": ["开放时间、票价与无障碍条件仍待官方核实"],
        "places": shown,
        "placesSource": {"provider": "AMAP", "query": keyword,
                         "retrievedAt": datetime.now(timezone.utc).isoformat()},
    }


def _tourism_result(invocation_id, value):
    """Wrap a trusted 8091 response in the v3 Result contract."""
    sources = value.get("sources", []) if isinstance(value.get("sources", []), list) else []
    pending = value.get("pendingChecks", []) if isinstance(value.get("pendingChecks", []), list) else []
    sources = [item for item in sources[:20] if isinstance(item, dict)]
    pending = [item for item in pending[:20] if isinstance(item, str) and item]
    availability = "REAL" if sources else "NEEDS_VERIFICATION"
    if not sources and "8091未提供可核验来源" not in pending:
        pending.append("8091未提供可核验来源")
    return {
        "resultId": "tourism-" + uuid.uuid5(uuid.NAMESPACE_URL, invocation_id).hex,
        "type": "TOURISM_ADVICE",
        "schemaVersion": "1.0",
        "title": "旅游咨询结果",
        "businessRef": None,
        "availability": availability,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
        "pendingChecks": pending,
        "payload": value,
    }


def _fraud_result(invocation_id, value):
    """Wrap a verified anti-fraud status without turning acceptance into a verdict."""
    completed=value.get('status')=='completed' and isinstance(value.get('result'),dict)
    return {
        "resultId": "fraud-" + uuid.uuid5(uuid.NAMESPACE_URL, invocation_id).hex,
        "type": "FRAUD_ANALYSIS",
        "schemaVersion": "1.0",
        "title": "反诈核实结果" if completed else "反诈任务处理状态",
        # P2's v3 response checker requires businessRef to stay null; the task
        # identity remains available in payload.analysis_id.
        "businessRef": None,
        "availability": "REAL" if completed else "NEEDS_VERIFICATION",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sources": [],
        "pendingChecks": [] if completed else ["反诈任务仍在处理，受理不代表已有风险结论"],
        "payload": value,
    }


def handle(request, planner=None, executor=None, domain_client=None):
    planner = planner or ask_model
    processing = []
    if not isinstance(request, dict) or request.get("protocolVersion") != "3.0":
        return failure("UNSUPPORTED_PROTOCOL_VERSION", "仅处理v3.0本地测试报文")
    try:
        task, context = request["task"], request["context"]
        if not all(isinstance(value, dict) for value in (task, context, request["input"])):
            raise ValueError()
        for key in ("userId", "conversationId", "messageId"):
            if not isinstance(request[key], str) or not request[key]:
                raise ValueError()
        for key in ("id", "invocationId"):
            if not isinstance(task[key], str) or not task[key]:
                raise ValueError()
        if type(task["version"]) is not int or task["version"] < 1:
            raise ValueError()
        deadline = datetime.fromisoformat(task["deadlineAt"].replace("Z", "+00:00"))
        if deadline.tzinfo is None:
            raise ValueError()
        if deadline <= datetime.now(timezone.utc):
            return failure("UPSTREAM_TIMEOUT", "调用截止时间已过；未调用模型")
        if task.get("parentTaskId") is not None:
            return failure("FORBIDDEN", "本适配器仅处理A1根任务")
        if request["input"].get("attachmentIds"):
            return failure("CAPABILITY_UNAVAILABLE", "本地适配器尚未实现附件受控读取")
        data = {
            "conversationId": request["conversationId"], "messageId": request["messageId"],
            "taskId": task["id"], "baseTaskVersion": task["version"],
            "invocationId": task["invocationId"], "intent": "tourism", "domains": [],
            "control": {"next": "COMPLETE", "outcome": "SUCCEEDED", "dependencyTaskIds": [], "inputRequest": None},
            "reply": {"text": "", "speechRate": 0.8, "audioUrl": None},
            "results": [], "confirmationIds": [], "tools": [], "handoff": None, "usedMemoryRefs": []
        }
        # Recovery is not safe without the server ledger/permissions and real gateway.
        raw_reason = context["reason"]
        if raw_reason not in ("USER_MESSAGE", "INPUT_PROVIDED", "CHILD_INPUT_REQUIRED",
                              "CHILD_CONFIRMATION_REQUIRED", "CHILDREN_FINISHED",
                              "CONFIRMATION_DECIDED", "RECOVERY"):
            return failure("CAPABILITY_UNAVAILABLE", "该恢复分支尚未接入P2，停止处理而不重跑任务")
        reason = route_reason(raw_reason)
        if reason == "CONFIRMATION_DECIDED":
            integrated = integrate_confirmation_decisions(
                task["id"], context.get("confirmationResults"), context.get("actionLedger"))
            data["control"].update(next="COMPLETE", outcome=integrated["outcome"])
            data["reply"]["text"] = integrated["reply"]
        elif reason == "RECOVERY":
            integrated = integrate_recovery(task["id"], context.get("actionLedger"))
            data["control"].update(next="COMPLETE", outcome=integrated["outcome"])
            data["reply"]["text"] = integrated["reply"]
        elif reason == "CHILDREN_FINISHED":
            integrated = integrate_dependencies(task["id"], context.get("dependencyResults"))
            data["control"].update(next="COMPLETE", outcome=integrated["outcome"])
            data["reply"]["text"] = integrated["reply"]
            data["results"] = integrated["results"]
            data["domains"] = integrated["domains"]
            data["intent"] = integrated["domains"][0] if integrated["domains"] else "tourism"
        elif reason == "CHILD_CONFIRMATION_REQUIRED":
            pending = collect_child_confirmations(task["id"], context.get("dependencyResults"))
            data["control"].update(next="WAIT_CONFIRMATION", outcome=None)
            data["confirmationIds"] = pending["confirmationIds"]
            data["domains"] = pending["domains"]
            data["intent"] = pending["domains"][0] if pending["domains"] else "care"
            data["reply"]["text"] = "协作任务有需要您决定的操作，请逐项核对后选择。"
        elif reason == "CHILD_INPUT_REQUIRED":
            pending = context.get("pendingInputRequests", [])
            if not pending:
                raise ValueError()
            q = pending[0]
            if (not isinstance(q, dict) or not question_id(q.get("inputRequestId"))
                    or not isinstance(q.get("ownerTaskId"), str) or not q["ownerTaskId"]
                    or q["ownerTaskId"] == task["id"]
                    or type(q.get("version")) is not int or q["version"] < 1
                    or not isinstance(q.get("question"), str) or not 0 < len(q["question"]) <= 4000
                    or not isinstance(q.get("requiredFields"), list) or len(q["requiredFields"]) > 10
                    or not all(isinstance(field, str) and 0 < len(field) <= 128 for field in q["requiredFields"])
                    or not isinstance(q.get("options"), list) or len(q["options"]) > 10
                    or type(q.get("allowFreeText")) is not bool):
                raise ValueError()
            for option in q["options"]:
                if (not isinstance(option, dict) or set(option) != {"id", "label", "value"}
                        or not all(isinstance(option[field], str) for field in option)
                        or not 0 < len(option["id"]) <= 128 or not 0 < len(option["label"]) <= 4000):
                    raise ValueError()
            # Present the same registered child question. The server must match the reference.
            proposal = {k: q[k] for k in ("inputRequestId", "question", "requiredFields", "options", "allowFreeText")}
            data["control"].update(next="WAIT_INPUT", outcome=None, inputRequest=proposal)
            data["reply"]["text"] = proposal["question"]
            domain = next((d.get("domain") for d in context.get("dependencyResults", []) if d.get("taskId") == q["ownerTaskId"]), None)
            data["domains"] = [domain] if domain else []
            data["intent"] = domain or "tourism"
        else:
            history = []
            if (not isinstance(context.get("history", []), list)
                    or not all(isinstance(line, dict) for line in context.get("history", []))):
                raise ValueError()
            for line in context.get("history", []):
                if line.get("role") in ("user", "assistant") and isinstance(line.get("text"), str):
                    history.append({"role": line["role"], "content": line["text"]})
            text = request["input"]["text"]
            hint = SINGLE_STEP_HINT
            continuation_prompt = None
            if new_travel_request(text):
                hint += "\n" + NEW_TRIP_HINT
            if reason == "INPUT_PROVIDED":
                answer = context["inputResponse"]
                if not isinstance(answer, dict) or not isinstance(answer.get("responseTo"), dict):
                    raise ValueError()
                reference = answer["responseTo"]
                selected = reference.get("selectedOptionId")
                if (not question_id(reference.get("inputRequestId"))
                        or type(reference.get("version")) is not int or reference["version"] < 1
                        # P2 的自由文本回答不带 selectedOptionId；它只在用户点选项时出现。
                        or ("selectedOptionId" in reference and selected is not None
                            and not isinstance(selected, str))):
                    raise ValueError()
                if reference.get("ownerTaskId") != task["id"]:
                    return failure("CAPABILITY_UNAVAILABLE", "回答不属于当前A1根任务，应由P2仅恢复对应问题所属子任务；未调用模型")
                text = answer["text"]
                # A resumed task must not replay destinations from older trips in
                # the same conversation. Keep this trip's opening request and
                # subsequent answers only; raw user evidence is unchanged.
                for index in range(len(history) - 1, -1, -1):
                    line = history[index]
                    if (line.get("role") == "user" and new_travel_request(line.get("content", ""))
                            and line.get('content', '').strip() not in ('帮我规划出行', '帮我安排旅游', '规划出行')):
                        history = history[index:]
                        break
                # 只回答一个词（如「长沙」）时，模型很容易把它当成旧行程的出发地。
                # 把上一轮问题原文作为本轮约束传给规划器；它只进入 system 提示，
                # 不进入用户历史，避免污染地点证据。
                pending = answer.get("question")
                question = pending.get("question") if isinstance(pending, dict) else None
                continuation_prompt = _pending_trip_prompt(text, question, history)
                if (isinstance(question, str) and 0 < len(question) <= 4000
                        and isinstance(text, str) and 0 < len(text.strip()) <= 200):
                    hint = SINGLE_STEP_HINT + "\n" + ANSWER_HINT % (question, text.strip())
                    if (re.search(r"哪个城市|哪座城市|目的地|哪个地点", question)
                            and not re.search(r"出发地|从哪", question)):
                        hint += ("\n本轮是在补充目的地，不是新请求。若回答已给出城市，"
                                 "location必须逐字取该城市原文（例如长沙市），不要把市中心附近拼接进城市名；"
                                 "不得再次询问城市。其他必要信息可以继续询问。")
                    hint += ("\n只询问执行当前任务所必需的缺失信息。普通景点查询不需要出发日期；"
                             "一日行程已有天数时，不得为查询景点强制追问具体日期。"
                             "用户已回答的信息不得重复询问；更改目的地时使用最新明确选择。")
            if not isinstance(text, str) or not text.strip() or len(text) > 2000:
                raise ValueError()
            # Reserve enough time for the model (default 40s), synchronous tourism
            # lookup (default 15s), validation and the HTTP response before P2's
            # approximately 65-second invocation deadline.
            if (deadline - datetime.now(timezone.utc)).total_seconds() < 58:
                return failure("UPSTREAM_TIMEOUT", "剩余调用预算不足58秒；未启动模型或领域服务")
            plan = ({'decision': 'ASK', 'reply': continuation_prompt, 'domains': ['tourism'],
                     'steps': [], 'memoryCandidate': None, 'location': None}
                    if continuation_prompt else _call_planner(planner, text, history, deadline, hint))
            processing.append('已识别待补充回答，未重复调用模型' if continuation_prompt
                              else '已取得并校验模型任务计划')
            if plan.get("decision") == "PLAN" and not _single_step_plan(plan):
                _log_plan_shape(plan, False)
                # One correction attempt with an explicit shape reminder, but only
                # when enough of P2's deadline budget is left for another model call.
                if (deadline - datetime.now(timezone.utc)).total_seconds() >= 25:
                    plan = _call_planner(planner, text, history, deadline,
                                         hint + "\n【步骤纠正】上一次计划包含多个步骤或依赖，当前无法执行。"
                                                "这次只输出一个可直接执行的步骤，或改为 ASK 向用户确认。")
                    _log_plan_shape(plan, _single_step_plan(plan))
            # A clarification such as "两天" does not repeat the trusted destination.
            # Only that destination's own user sentence is reused, never unrelated
            # older cities or assistant prose.
            tourism_source = _tourism_source(text, plan.get("location"), history)
            data["domains"] = plan["domains"]
            data["intent"] = plan["domains"][0] if plan["domains"] else "tourism"
            if plan["decision"] == "ASK":
                data["control"].update(next="WAIT_INPUT", outcome=None, inputRequest={
                    "inputRequestId": str(uuid.uuid4()),
                    "question": plan["reply"], "requiredFields": ["clarification"],
                    "options": plan.get("options") or [], "allowFreeText": True
                })
                data["reply"]["text"] = plan["reply"]
            elif plan["decision"] == "PLAN":
                steps = plan["steps"]
                if (len(steps) == 1 and steps[0].get("agent") == "a1"
                        and steps[0].get("domain") == "tourism"
                        and not steps[0].get("dependsOn")):
                    client = domain_client or DomainClient()
                    # 用户只回了一个城市（如「长沙」）时，8091 的对话接口需要景点 ID，
                    # 拿城市当位置只会返回演示资料或含糊反问；直接用高德按城市查真实地点。
                    tourism = None
                    if (isinstance(text, str) and isinstance(plan.get("location"), str)
                            and text.strip() == plan["location"].strip()):
                        tourism = _place_recommendation(client, plan.get("location"), text)
                    if tourism is None:
                        try:
                            tourism = client.tourism(tourism_source, location=plan.get("location"))
                        except DomainError as error:
                            tourism = (_place_recommendation(client, plan.get("location"), text, force=True)
                                       if "演示" in str(error) else None)
                            if tourism is None:
                                raise
                    if (not tourism.get("sources")
                            and re.search(r"没有查到|未找到|没有找到|不知道您(?:的)?位置|尚未选中真实地点|您想了解哪个地点",
                                          tourism.get("text", ""))):
                        fallback = _place_recommendation(client, plan.get("location"), text, force=True)
                        if fallback is not None:
                            tourism = fallback
                    # 目的地已经确认，回复却反问「还没告诉我具体想去哪里」：上下文已经串了，
                    # 改用高德真实地点回答同一目的地，避免老人看到自相矛盾的内容。
                    if DESTINATION_DENIED.search(str(tourism.get("text", ""))):
                        fallback = _place_recommendation(client, plan.get("location"), text, force=True)
                        if fallback is not None:
                            tourism = fallback
                    data["control"].update(next="COMPLETE", outcome="SUCCEEDED")
                    reply_text = _plain_text(tourism["text"])
                    data["reply"]["text"] = reply_text if len(reply_text) <= 4000 else reply_text[:3999] + "…"
                    card = _tourism_result(task["invocationId"], tourism)
                    _attach_places(card, client, plan.get("location"), text)
                    data["results"] = [card]
                    processing.append('旅游查询已返回；来源和待核实项保留在结果中')
                    # A real place lookup is only an intermediate result when
                    # the user requested an itinerary. Never label that as a
                    # completed, accessibility-verified travel plan.
                    if (tourism.get('places') and re.search(r'规划|行程|安排.*(?:旅游|出行)', tourism_source)):
                        options = [{'id': 'place-' + str(i), 'label': p['name'], 'value': p['name']}
                                   for i, p in enumerate(tourism['places'][:6])
                                   if isinstance(p, dict) and isinstance(p.get('name'), str)]
                        question = '已查到候选地点，行程尚未完成。您想先了解哪一个地点？少走路及休息设施还需要进一步核实。'
                        data['control'].update(next='WAIT_INPUT', outcome=None, inputRequest={
                            'inputRequestId': str(uuid.uuid4()), 'question': question,
                            'requiredFields': ['selectedPlace'], 'options': options, 'allowFreeText': True})
                        data['reply']['text'] += '\n\n' + question
                        draft = _itinerary_draft(tourism, plan.get('location'), text, history)
                        if draft:
                            card['payload']['itineraryDraft'] = draft['days']
                            card['pendingChecks'].append('行程草案尚未确认；未核实步行路线及休息设施')
                            data['reply']['text'] = draft['text']
                            data['control']['inputRequest'].update(
                                question=draft['question'], requiredFields=[draft['requiredField']], options=[])
                elif (len(steps) == 1 and steps[0].get("agent") == "a1"
                        and steps[0].get("domain") == "fraud"
                        and not steps[0].get("dependsOn")):
                    client = domain_client or DomainClient()
                    receipt = client.fraud(text)
                    try:configured_wait=float(os.environ.get('A1_FRAUD_WAIT_SECONDS','45'))
                    except ValueError:raise DomainError('A1_FRAUD_WAIT_SECONDS 配置无效') from None
                    if not 0 <= configured_wait <= 50:
                        raise DomainError('A1_FRAUD_WAIT_SECONDS 必须在0至50秒之间')
                    remaining=max(0,(deadline-datetime.now(timezone.utc)).total_seconds()-5)
                    stop=time.monotonic()+min(configured_wait,remaining)
                    status=client.status()
                    while status.get('status') in ('queued','processing') and time.monotonic()<stop:
                        time.sleep(min(1,max(0,stop-time.monotonic())))
                        status=client.status()
                    completed=status.get('status')=='completed'
                    data["control"].update(next="COMPLETE",outcome="SUCCEEDED" if completed else "PARTIALLY_SUCCEEDED")
                    data["reply"]["text"]=("反诈分析已完成，请结合原文证据核对。" if completed
                                             else "反诈任务已受理但仍在处理；当前没有风险结论，请稍后按任务编号查询。")
                    data["results"]=[_fraud_result(task["invocationId"],status)]
                    processing.append('反诈服务已返回任务状态；受理与分析完成分别核对')
                elif any(step.get("agent") == "a1" for step in steps):
                    # 模型偶尔仍会把一个需求拆成多步。这里不能报应用级错误（P2 会
                    # 显示“调用结果未确认”），改为合法的追问，把任务收敛到一个可执行步骤。
                    _log_plan_shape(plan, False)
                    question = ("这个需求包含多项内容，当前版本一次只能完成一项查询。"
                                "请再说明这次最想先办的一件事，例如只查一个城市的景点或只做反诈分析。")
                    data["control"].update(next="WAIT_INPUT", outcome=None, inputRequest={
                        "inputRequestId": str(uuid.uuid4()), "question": question,
                        "requiredFields": ["clarification"], "options": [], "allowFreeText": True
                    })
                    data["reply"]["text"] = question
                else:
                    if executor is None:
                        key = os.environ.get("A1_AGENT_KEY")
                        token = request.get("capabilityToken")
                        if key and isinstance(token, str) and token.strip():
                            executor = PlanExecutor(P2Client(key=key, context_token=token,
                                                             trace_id=task["invocationId"]))
                    if executor is None:
                        return failure("CAPABILITY_UNAVAILABLE", "已形成内部计划，但P2委派凭证未配置；未创建子任务或执行业务")
                    children = executor.delegate_children(
                        conversation_id=request["conversationId"], task_id=task["id"],
                        task_version=task["version"], invocation_id=task["invocationId"],
                        plan=plan,
                    )
                    data["control"].update(next="WAIT_DEPENDENCIES", outcome=None,
                                           dependencyTaskIds=[child["childTaskId"] for child in children])
                    data["reply"]["text"] = "已通过P2创建协作子任务，正在等待结果。"
            else:
                data["reply"]["text"] = plan["reply"]
        if processing:
            state_label = {'WAIT_INPUT': '等待您补充信息', 'WAIT_DEPENDENCIES': '等待协作任务结果',
                           'COMPLETE': '本次处理已返回，仍需查看结果中的待核实项'}.get(data['control']['next'], '等待后续处理')
            summary = {'kind': 'EXECUTION_SUMMARY', 'invocationId': task['invocationId'],
                       'events': processing, 'state': state_label,
                       'internalReasoning': False}
            for card in data['results']:
                if card.get('type') in ('TOURISM_ADVICE', 'FRAUD_ANALYSIS') and isinstance(card.get('payload'), dict):
                    card['payload']['processingSummary'] = summary
            note = '\n\n处理记录：' + '；'.join(processing) + '。当前：' + state_label + '。'
            reply = data['reply']['text']
            truncated = reply.endswith('…') or len(reply) + len(note) > 4000
            data['reply']['text'] = reply[:max(0, 4000-len(note)-(1 if truncated else 0))] + note + ('…' if truncated else '')
        return {"code": "OK", "message": "本地报文适配完成，非运行中的业务网关", "data": data}
    except PlanningError:
        return failure("UPSTREAM_ERROR", "模型调用或规划校验失败，未执行业务")
    except P2Error as error:
        return failure("UPSTREAM_ERROR", str(error))
    except DomainError as error:
        return failure("UPSTREAM_ERROR", str(error))
    except (KeyError, TypeError, ValueError, IndexError):
        return failure("INVALID_ARGUMENT", "测试报文缺字段、类型错误或上下文不完整")


def main():
    parser = argparse.ArgumentParser(description="离线测试v3报文，不启动服务，不执行P2业务")
    parser.add_argument("file", help="测试InvocationRequest JSON路径")
    args = parser.parse_args()
    try:
        with open(args.file, encoding="utf-8") as source:
            result = handle(json.load(source))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["code"] == "OK" else 1
    except (OSError, ValueError):
        print("无法读取有效JSON测试文件", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
