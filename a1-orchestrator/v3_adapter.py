"""Offline r3 packet adapter. Not an HTTP service or a P2 replacement."""
import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from a1 import ask_model, PlanningError
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


def handle(request, planner=None, executor=None, domain_client=None):
    planner = planner or ask_model
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
            if reason == "INPUT_PROVIDED":
                answer = context["inputResponse"]
                if not isinstance(answer, dict) or not isinstance(answer.get("responseTo"), dict):
                    raise ValueError()
                reference = answer["responseTo"]
                if (not question_id(reference.get("inputRequestId"))
                        or type(reference.get("version")) is not int or reference["version"] < 1
                        or "selectedOptionId" not in reference
                        or reference["selectedOptionId"] is not None and not isinstance(reference["selectedOptionId"], str)):
                    raise ValueError()
                if reference.get("ownerTaskId") != task["id"]:
                    return failure("CAPABILITY_UNAVAILABLE", "回答不属于当前A1根任务，应由P2仅恢复对应问题所属子任务；未调用模型")
                history.append({"role": "user", "content": text})
                text = answer["text"]
            if not isinstance(text, str) or not text.strip() or len(text) > 2000:
                raise ValueError()
            # Reserve enough time for the model (default 40s), synchronous tourism
            # lookup (default 15s), validation and the HTTP response before P2's
            # approximately 65-second invocation deadline.
            if (deadline - datetime.now(timezone.utc)).total_seconds() < 58:
                return failure("UPSTREAM_TIMEOUT", "剩余调用预算不足58秒；未启动模型或领域服务")
            plan = planner(text, history)
            data["domains"] = plan["domains"]
            data["intent"] = plan["domains"][0] if plan["domains"] else "tourism"
            if plan["decision"] == "ASK":
                data["control"].update(next="WAIT_INPUT", outcome=None, inputRequest={
                    "inputRequestId": str(uuid.uuid4()),
                    "question": plan["reply"], "requiredFields": ["clarification"],
                    "options": [], "allowFreeText": True
                })
                data["reply"]["text"] = plan["reply"]
            elif plan["decision"] == "PLAN":
                steps = plan["steps"]
                if (len(steps) == 1 and steps[0].get("agent") == "a1"
                        and steps[0].get("domain") == "tourism"
                        and not steps[0].get("dependsOn")):
                    client = domain_client or DomainClient()
                    tourism = client.tourism(text, location=plan.get("location"))
                    data["control"].update(next="COMPLETE", outcome="SUCCEEDED")
                    reply_text = tourism["text"]
                    data["reply"]["text"] = reply_text if len(reply_text) <= 4000 else reply_text[:3999] + "…"
                    data["results"] = [_tourism_result(task["invocationId"], tourism)]
                elif any(step.get("agent") == "a1" for step in steps):
                    return failure("CAPABILITY_UNAVAILABLE", "A1 v3首轮仅接通单步旅游文本；未执行其他步骤")
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
