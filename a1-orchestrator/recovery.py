"""根据 P2 权威确认和动作账本形成恢复结果，绝不重放业务动作。"""
from p2_client import P2Error


def _valid_id(value):
    return isinstance(value, str) and 0 < len(value) <= 128


def integrate_confirmation_decisions(root_task_id, confirmations, ledger):
    if not isinstance(confirmations, list) or not confirmations or len(confirmations) > 20:
        raise P2Error("confirmationResults 数量无效")
    if not isinstance(ledger, list) or len(ledger) > 40:
        raise P2Error("actionLedger 格式无效")
    actions = {}
    for item in ledger:
        if not isinstance(item, dict) or not _valid_id(item.get("actionId")):
            raise P2Error("动作账本条目无效")
        if item["actionId"] in actions:
            raise P2Error("动作账本存在重复actionId")
        actions[item["actionId"]] = item
    lines, successes, failures = [], 0, 0
    for item in confirmations:
        if (not isinstance(item, dict) or item.get("rootTaskId") != root_task_id
                or item.get("ownerTaskId") != root_task_id or not _valid_id(item.get("confirmationId"))
                or not _valid_id(item.get("actionId")) or type(item.get("version")) is not int
                or item["version"] < 1):
            raise P2Error("确认结果无效或不属于当前A1根任务")
        state, action_status = item.get("state"), item.get("actionStatus")
        summary = item.get("summary")
        if not isinstance(summary, str) or not summary:
            raise P2Error("确认结果缺少操作摘要")
        action = actions.get(item["actionId"])
        if state == "EXECUTED" and action_status == "SUCCEEDED":
            if not action or action.get("executionStatus") != "SUCCEEDED":
                raise P2Error("确认结果与动作账本不一致")
            successes += 1;lines.append(summary + "：已执行")
        elif state in ("REJECTED", "CANCELLED", "EXPIRED", "INVALIDATED"):
            failures += 1;lines.append(summary + "：" + {"REJECTED":"已拒绝","CANCELLED":"已取消","EXPIRED":"已过期","INVALIDATED":"已失效"}[state])
        elif state == "EXECUTION_FAILED" and action_status == "FAILED":
            if not action or action.get("executionStatus") != "FAILED":
                raise P2Error("确认失败状态与动作账本不一致")
            failures += 1
            error = item.get("lastError")
            message = error.get("message") if isinstance(error, dict) else None
            lines.append(summary + "：执行失败" + ("（%s）" % message if isinstance(message, str) and message else ""))
        else:
            raise P2Error("确认动作仍在执行或结果未知，需由P2继续核查，未重放动作")
    outcome = "SUCCEEDED" if successes and not failures else "PARTIALLY_SUCCEEDED" if successes else "FAILED"
    return {"outcome": outcome, "reply": "\n".join(lines)[:1500]}


def integrate_recovery(root_task_id, ledger):
    if not isinstance(ledger, list) or not ledger or len(ledger) > 40:
        raise P2Error("恢复缺少可核查的动作账本")
    lines, successes, failures = [], 0, 0
    for item in ledger:
        if (not isinstance(item, dict) or not _valid_id(item.get("actionId"))
                or not _valid_id(item.get("tool"))):
            raise P2Error("动作账本条目无效")
        status = item.get("executionStatus")
        if status in ("RUNNING", "UNKNOWN"):
            raise P2Error("动作仍在运行或结果未知，需先按actionId核查，未重放动作")
        if status in ("PREPARED", "NOT_STARTED"):
            raise P2Error("动作尚未执行，恢复需要原计划参数与有效凭证，未自动重放")
        if status == "SUCCEEDED":
            successes += 1;lines.append(item["tool"] + "：已完成")
        elif status == "FAILED":
            failures += 1
            error = item.get("lastError")
            message = error.get("message") if isinstance(error, dict) else None
            lines.append(item["tool"] + "：失败" + ("（%s）" % message if isinstance(message, str) and message else ""))
        else:
            raise P2Error("动作账本执行状态无效")
    outcome = "SUCCEEDED" if successes and not failures else "PARTIALLY_SUCCEEDED" if successes else "FAILED"
    return {"outcome": outcome, "reply": "恢复核查结果：\n" + "\n".join(lines)[:1470]}

