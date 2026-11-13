"""把已校验的 A2/A3 计划转换为 P2 登记、动作准备和委派。"""
import hashlib
import json

from p2_client import P2Error


def select_dependency_wave(plan, *, completed_step_ids=(), failed_step_ids=(),
                           dispatched_step_ids=()):
    """Select the next safe DAG wave without guessing any P2 task mapping.

    A step is ready only when all prerequisites succeeded.  A failed or blocked
    prerequisite blocks every transitive dependent.  Dispatched steps are never
    returned again, which lets callers preserve P2's idempotency boundary.
    """
    steps = plan.get("steps") if isinstance(plan, dict) else None
    if not isinstance(steps, list) or not steps:
        raise P2Error("计划没有可调度步骤")
    by_id = {}
    ordered_ids = []
    for step in steps:
        if (not isinstance(step, dict) or not isinstance(step.get("id"), str)
                or not step["id"] or step["id"] in by_id
                or not isinstance(step.get("dependsOn"), list)
                or not all(isinstance(value, str) and value for value in step["dependsOn"])
                or len(set(step["dependsOn"])) != len(step["dependsOn"])):
            raise P2Error("计划步骤或依赖格式无效")
        if any(value not in by_id for value in step["dependsOn"]):
            raise P2Error("计划依赖必须引用此前步骤")
        by_id[step["id"]] = step
        ordered_ids.append(step["id"])

    completed = set(completed_step_ids)
    failed = set(failed_step_ids)
    dispatched = set(dispatched_step_ids)
    known = set(by_id)
    if (completed & failed or not completed <= known or not failed <= known
            or not dispatched <= known):
        raise P2Error("P2步骤状态与当前计划不一致")

    blocked = set(failed)
    changed = True
    while changed:
        changed = False
        for sid in ordered_ids:
            if sid not in blocked and any(dep in blocked for dep in by_id[sid]["dependsOn"]):
                blocked.add(sid)
                changed = True

    ready = []
    pending = []
    for sid in ordered_ids:
        if sid in completed or sid in blocked or sid in dispatched:
            continue
        if all(dep in completed for dep in by_id[sid]["dependsOn"]):
            ready.append(by_id[sid])
        else:
            pending.append(by_id[sid])
    return {
        "ready": ready,
        "blockedStepIds": [sid for sid in ordered_ids if sid in blocked],
        "pendingStepIds": [step["id"] for step in pending],
    }


def _delegation_input(step):
    return {
        "targetAgent": step["agent"],
        "domain": step["domain"],
        "required": True,
        "instruction": step["goal"],
        "attachmentIds": [],
        "businessRefs": [],
    }


def _request_key(invocation_id, plan):
    digest = hashlib.sha256(json.dumps(plan, ensure_ascii=False, sort_keys=True,
                                       separators=(",", ":")).encode("utf-8")).hexdigest()[:24]
    return "plan-%s-%s" % (invocation_id[:48], digest)


class PlanExecutor:
    def __init__(self, p2):
        self.p2 = p2

    def delegate_children(self, *, conversation_id, task_id, task_version,
                          invocation_id, plan):
        steps = plan.get("steps") if isinstance(plan, dict) else None
        if not isinstance(steps, list) or not steps:
            raise P2Error("计划没有可登记步骤")
        if any(step.get("agent") not in ("a2", "a3") for step in steps):
            raise P2Error("首批P2计划执行器只处理A2/A3委派")
        if any(step.get("dependsOn") for step in steps):
            raise P2Error("含前后依赖的子任务需分轮执行，首批未并发委派")
        registered_steps = []
        inputs = {}
        for step in steps:
            delegation = _delegation_input(step)
            inputs[step["id"]] = delegation
            registered_steps.append({"clientStepKey": step["id"], "tool": "agent.delegate",
                                     "args": delegation})
        registered = self.p2.register_steps(
            task_id, _request_key(invocation_id, plan), 1, registered_steps
        )
        mappings = registered.get("steps") if isinstance(registered, dict) else None
        if not isinstance(mappings, list) or len(mappings) != len(registered_steps):
            raise P2Error("P2步骤登记结果不完整，未准备委派")
        by_key = {}
        for item in mappings:
            if (not isinstance(item, dict) or item.get("clientStepKey") in by_key
                    or not isinstance(item.get("stepId"), str) or not item["stepId"]
                    or not isinstance(item.get("prepareKey"), str) or not item["prepareKey"]):
                raise P2Error("P2步骤登记结果无效，未准备委派")
            by_key[item["clientStepKey"]] = item
        if set(by_key) != set(inputs):
            raise P2Error("P2步骤映射与当前计划不一致，未准备委派")
        children = []
        for step in steps:
            mapping = by_key[step["id"]]
            delegation = inputs[step["id"]]
            action = self.p2.prepare_action(
                task_id, mapping["stepId"],
                {"tool": "agent.delegate", "args": delegation},
                mapping["prepareKey"],
            )
            if (not isinstance(action, dict) or not isinstance(action.get("actionId"), str)
                    or not action["actionId"]):
                raise P2Error("P2未返回有效actionId，未创建子任务")
            if action.get("requiresConfirmation") is True:
                raise P2Error("P2要求先确认委派动作，本轮未创建子任务")
            child = self.p2.delegate(
                conversation_id, task_id, action["actionId"], delegation
            )
            if (not isinstance(child, dict) or not isinstance(child.get("childTaskId"), str)
                    or not child["childTaskId"]):
                raise P2Error("P2未返回有效childTaskId")
            children.append(child)
        return children

